#
# TextureExporter
#
# Author : Chia Xin Lin (nnnight@gmail.com)
#
# Version : 0.1.0 (beta)
#
# First Build : 2020/09/18
# Last Updated: 2020/10/01
#
# Substance Painter Version : 2020.2.0 (6.2.0)
#
#

from PySide2 import QtWidgets, QtGui, QtCore
from os.path import dirname, basename, join, isdir, isfile, realpath
import CxLd.ui
import CxLd.meta
import subprocess
import multiprocessing              as mp
import json
import os
import re
import substance_painter.ui         as spui
import substance_painter.event      as spev
import substance_painter.project    as sppj
import substance_painter.textureset as spts
import substance_painter.export     as spex
import substance_painter.logging    as splg

# -----------------------------------------
__Version__= '0.1.0 (beta)'
__Author__ = "Chia Xin Lin"
__Email__  = "nnnight@gmail.com"
__Contact__= "https://github.com/chiaxin"
__Title__  = 'Texture Exporter'
# -----------------------------------------

PluginWidgets = []

__DEBUG__ = True

_ExportConfigFile = "ExportConfig.json"

_IconImageFile = join(
    dirname(realpath(__file__)),
    "icons",
    "TextureExportIcon.svg"
)
_ProjIconFile = join(
    dirname(realpath(__file__)),
    "icons",
    "CxldTeProjectIcon.svg"
)

_GlobalLabelStyle = """
    background-color: rgba(188, 188, 150, 100);
    font: bold 16px;
    selection-color: yellow;
    border-radius : 8px;
    max-height : 30px;
    min-width : 120px;
    padding-left : 10px;
"""

_GlobalAreaStyle = """
    background-color: rgba(188, 188, 150, 100);
    font: bold 16px;
    border-radius: 8px;
    padding-left : 12px;
"""

_GlobalButtonStyle = """
    background-color: rgba(188, 188, 150, 100);
    border-radius: 3px;
    font: bold 12px
"""

_GlobalCheckBoxStyle = """
"""

_GlobalLineEditStyle = """
    background-color: rgba(88, 88, 88, 100);
    selection-background-color: rgba(120, 120, 120, 100);
    border-color: rgba(150, 150, 150, 100);
    border-style: outset;
    border-width: 1px;
    border-radius: 2px;
    font: bold 14px;
    padding: 4px;
    min-height: 16px
"""

_MeshMaps = [
    "ambient_occlusion",
    "id",
    "curvature",
    "normal_base",
    "world_space_normals",
    "position",
    "thickness"
]

ExportChannelRangeKeeper = CxLd.meta.Metadata("Export_Channel_Ranges")

# Debug functions :
def _log_channel_map(channel_map):
    if isinstance(channel_map, dict)\
    and "destChannel" in channel_map\
    and "srcChannel"  in channel_map\
    and "srcMapType"  in channel_map\
    and "srcMapName"  in channel_map:
        print("Dest : {0}, Src : {1}, Type : {2}, Map : {3}".format(
            channel_map["destChannel"],
            channel_map["srcChannel"],
            channel_map["srcMapType"],
            channel_map["srcMapName"]
            )
        )
    else:
        print("Failed to get channel map.\n")
#

def log(message):
    splg.info(message)

def warn(message):
    splg.warning(message)

def err(message):
    splg.error(message)

def is_udim(name):
    return re.match(r"^[1-9]\d{3}$", name)

def clean_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        else:
            clean_layout(item.layout())

class ExportSettingNoFoundError(Exception):
    pass

class ExportSettingError(Exception):
    pass

class ExportConfig(object):
    Limits = {
        "output_size"           : [512, 1024, 2048, 8192, 4096],
        "export_format"         : ["png", "tga", "jpg", "tif"],
        "normal_map"            : ["directx", "open_gl"],
        "export_shader_params"  : [1, 0],
        "dithering"             : [0, 1],
        "padding_algorithm"     : [
            "passthrough", "color", "transparent", "diffusion", "infinite"
        ]
    }
    def __init__(self):
        super().__init__()
        self.settings = None
        self.config_file = join(dirname(realpath(__file__)), _ExportConfigFile)
        if isfile(self.config_file):
            with open(self.config_file, 'r') as file_handle:
                try:
                    data = json.load(file_handle)
                except Exception as e:
                    raise e
                else:
                    self.settings = data
        else:
            err("Can't get export config file : {0}".format(self.config_file))
            raise ExportSettingNoFoundError()

    def is_executable(self, file):
        return isfile(file) and os.access(file, os.X_OK)

    def value(self, key):
        if key not in self.settings:
            raise ExportSettingNoFoundError("Failed to get setting : %s" % key)
        value = self.settings[key]
        if key in ExportConfig.Limits.keys():
            if value not in ExportConfig.Limits[key]:
                value = ExportConfig.Limits[key][-1]
        return value

    def converter_is_exists(self):
        return self.is_executable(self.value("converter"))

try:
    Settings = ExportConfig()
    ProjectNameMatcher = re.compile(Settings.value("naming"))
    ConfigName          = Settings.value("configName")
    Converter           = Settings.value("converter")
    ExportName          = Settings.value("export_name")
    LegacyName          = Settings.value("legacy_name")
    MeshMapName         = Settings.value("meshmap_name")
    ExportDirectory     = Settings.value("export_path")
    ConvertDirectory    = Settings.value("convert_path")
    MeshMapDirectory    = Settings.value("meshmap_path")
    OutputSize          = Settings.value("output_size")
    ExportFormat        = Settings.value("export_format")
    ConvertFormat       = Settings.value("convert_format")
    ChannelMaps         = Settings.value("maps")
    NormalMapFormat     = Settings.value("normal_map")
    ExportPreset        = Settings.value("preset")
    ExportShaderParams  = Settings.value("export_shader_params") == 1
    Dithering           = Settings.value("dithering") == 1
    DilationDistance    = Settings.value("dilationDistance")
    PaddingAlgorithm    = Settings.value("paddingAlgorithm")
except ExportSettingNoFoundError as error:
    print(error)

class Workflow(object):
    Successful = 0
    NameIsNotCorrect = 1
    ProjectNotOpened = 2
    def __init__(self):
        super().__init__()
        if sppj.is_open():
            self.project = sppj.file_path()
            self.basename= basename(self.project)
            self.title = ""
            self.valid = True
        else:
            self.project = ""
            self.basename = ""
            self.title = ""
            self.valid = False
        matcher = ProjectNameMatcher.match(self.basename)
        if matcher:
            self.title = matcher.group(1)
            self.valid = True
        else:
            log("Naming format is not correct : {0}".format(self.basename))
            self.valid = False

    def name(self):
        if sppj.is_open():
            return self.basename
        return ""

    def get_title(self):
        if self.title:
            return self.title
        return ""

    def status(self):
        # If project is opened and name is matched, return 0 (Successful).
        # Opened but name is not matched, return 1 (Name is not correct).
        # Project is not opened, return 2 (Project not opened).
        if sppj.is_open() and self.valid:
            return Workflow.Successful
        elif sppj.is_open():
            return Workflow.NameIsNotCorrect
        else:
            return Workflow.ProjectNotOpened

    def get_previous_directory(self):
        if self.project:
            return dirname(dirname(self.project)).replace('\\', '/')
        else:
            return None

    def get_output_directory(self):
        previous = self.get_previous_directory()
        if previous:
            return join(previous, ExportDirectory).replace('\\', '/')
        return None

    def get_convert_directory(self):
        previous = self.get_previous_directory()
        if previous:
            return join(previous, ConvertDirectory).replace('\\', '/')
        return None

    def get_meshmap_directory(self):
        previous = self.get_previous_directory()
        if previous:
            return join(previous, MeshMapDirectory).replace("\\", "/")
        return None

class Exporter(Workflow):
    def __init__(self, shader, shader_name="",
        parse="", with_convert=False, force_8_bits=False
    ):
        super().__init__()
        self.shader = shader
        self.shader_name = shader_name
        self.scope_map = {}
        self.with_convert = with_convert
        self.force_8_bits = force_8_bits
        self.texture_set = TextureSetWrapper(
            spts.TextureSet.from_name(self.shader)
        )
        self.channel_maps = self.texture_set.get_channels()
        if parse:
            self.scope_map = self.get_channel_udim_range(parse)
        self.output_path = self.get_output_directory()
        self.convert_path = self.get_convert_directory()
        self.meshmap_path = self.get_meshmap_directory()
        self.create_directory(self.output_path)

    def get_title(self):
        if not self.title:
            return ""
        title = self.title
        if not is_udim(self.shader):
            title = title + "_$textureSet"
        return title

    def get_export_name(self, channel_name):
        title = self.get_title()
        export_name = ExportName
        if is_udim(self.shader):
            export_name = LegacyName
            if export_name.find("$shader") >= 0:
                export_name = export_name.replace("$shader", self.shader_name)
        if __DEBUG__: print("Export : {0}".format(export_name))
        return export_name.format(title, channel_name)

    def get_channel_maps(self):
        maps = []
        bit_depth_8_list = (
            "ChannelFormat.sRGB8",
            "ChannelFormat.L8",
            "ChannelFormat.RGB8"
        )
        bit_depth_16_list= (
            "ChannelFormat.L16",
            "ChannelFormat.RGB16",
            "ChannelFormat.L16F",
            "ChannelFormat.RGB16F"
        )
        bit_depth_32_list= (
            "ChannelFormat.L32F",
            "ChannelFormat.RGB32F"
        )
        texture_set = self.texture_set
        for label, channel in self.channel_maps.items():
            if __DEBUG__: print("Channel : {0}".format(label))
            src_map_type = "documentMap"
            if label.lower() not in ChannelMaps:
                continue
            channel_name = ChannelMaps.get(label.lower(), None)
            if not channel_name:
                continue
            src_map_name = label.lower()
            if src_map_name == "normal":
                src_map_type = "virtualMap"
                if NormalMapFormat == "open_gl":
                    src_map_name = "Normal_OpenGL"
                elif NormalMapFormat == "directx":
                    src_map_name = "Normal_DirectX"
                else:
                    src_map_type = "documentMap"
            channel_format = channel.format()
            indivduals = ('R', 'G', 'B')
            if str(channel_format).startswith('L'):
                indivduals = ('L')
            ch_describe = dict()
            ch_describe['fileName'] = self.get_export_name(channel_name)
            channels = []
            parameters = {}
            if self.force_8_bits:
                parameters["bitDepth"] = "8"
            else:
                channel_format = channel.format()
                fmt_value = str(channel_format)
                if fmt_value in bit_depth_8_list:
                    parameters["bitDepth"] = "8"
                elif fmt_value in bit_depth_16_list:
                    parameters["bitDepth"] = "16"
                elif fmt_value in bit_depth_32_list:
                    parameters["bitDepth"] = "32"
                log("{0}.{1} bit depth : {2}".format(
                    self.shader, channel, parameters["bitDepth"]
                ))
            for single in indivduals:
                channel_description = {
                        "destChannel": single,
                        "srcChannel" : single,
                        "srcMapType" : src_map_type,
                        "srcMapName" : src_map_name
                    }
                channels.append(channel_description)
            ch_describe['channels'] = channels
            ch_describe['parameters'] = parameters
            maps.append(ch_describe)
        return maps

    def get_export_list_test(self):
        return [{
            "rootPath" : self.shader,
            "filter" : {
                "outputMaps" : [self.get_export_name("C1")],
                "uvTiles" : [[0, 0]]
            }
        }]

    def get_export_list(self):
        export_list = []
        output_maps = []
        uv_tiles = []
        root_path = self.shader
        if self.scope_map:
            if "*" in self.scope_map:
                uv_tiles = self.scope_map["*"]
                export_list.append({
                    "rootPath" : root_path,
                    "filter" : {
                        "uvTiles" : uv_tiles
                    }
                })
            else:
                for channel in self.scope_map.keys():
                    if channel not in ChannelMaps:
                        continue
                    uv_tiles = self.scope_map[channel]
                    short = ChannelMaps[channel]
                    export_list.append({
                        "rootPath"   : root_path,
                        "filter" : {
                            "outputMaps" : [self.get_export_name(short)]
                        }
                    })
                    if uv_tiles:
                        export_list[-1]["filter"]["uvTiles"] = uv_tiles
                    else:
                        log("Export all udim - {0} : {1}".format(
                            self.shader, channel
                            )
                        )
        else:
            export_list = [{ "rootPath" : root_path }]
        return export_list

    def get_size(self):
        if OutputSize == 4096:
            return 12
        elif OutputSize == 2048:
            return 11
        elif OutputSize == 1024:
            return 10
        elif OutputSize == 512:
            return 9
        else:
            raise

    def get_channel_udim_range(self, expression=""):
        udim_expression = r"(\*|(?:[1-9]\d{3})(?:-[1-9]\d{3})?)"
        channel_expression = r"(\w[\w\d]+|\*)"
        parser = channel_expression + ":" + udim_expression
        expressions = re.findall(parser, expression)
        range_maps = {}
        normalize_u = lambda udim: (udim - 1001) % 10
        normalize_v = lambda udim: (udim - 1001)// 10
        is_wildcard_setup = False
        for pair in expressions:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                warn("Failed to parsing range : list of pair is not 2 items.")
                continue
            channel, udims = pair
            # Parsing channel
            if channel == "*":
                is_wildcard_setup = True
            elif channel not in ChannelMaps.keys():
                warn("[Parsing Range] The channel is not in list : ".format(
                        channel
                    )
                )
                continue
            udim_range_buffers = []
            # Parsing udim
            # A range matched : diffuse:1001-1010
            if re.match(r"[1-9]\d{3}-[1-9]\d{3}", udims):
                start, end = [ int(temp) for temp in udims.split("-") ]
                if end <= start:
                    print("[Parsing Range] Invalid udim range : {0}-{1}".format(
                        start, end
                    ))
                    continue
                numbers = range(start, end + 1)
                udim_range_buffers = [
                    [normalize_u(num), normalize_v(num)] for num in numbers
                ]
            # A udim number matched : diffuse:1002
            elif re.match(r"[1-9]\d{3}", udims):
                number = int(udims)
                udim_range_buffers = [
                    [normalize_u(number), normalize_v(number)]
                ]
            # A wildcard matched : diffuse:*
            elif udims == "*":
                udim_range_buffers = []
            else:
                warn("[Parsing Range] Invalid range expression : {0}".format(
                    udims
                ))
            if channel in range_maps:
                range_maps[channel].extend(udim_range_buffers)
            else:
                range_maps[channel] = udim_range_buffers
        if is_wildcard_setup:
            for channel in self.channel_maps:
                if channel not in range_maps:
                    range_maps[channel] = []
        return range_maps

    def get_meshmaps(self, is_combined=False):
        title = self.get_title()
        maps = []
        texture_set = TextureSetWrapper(spts.TextureSet.from_name(self.shader))
        for meshmap in _MeshMaps:
            ch_describe = dict()
            ch_describe["fileName"] = MeshMapName.format(title, meshmap)
            channels = []
            for single in ["R", "G", "B"]:
                channel_description = {
                    "destChannel": single,
                    "srcChannel" : single,
                    "srcMapType" : "meshMap",
                    "srcMapName" : meshmap
                }
                channels.append(channel_description)
            ch_describe['channels'] = channels
            maps.append(ch_describe)
        return maps

    def get_export_texture_presets(self):
        return { "name" : ExportPreset, "maps" : self.get_channel_maps() }

    def get_export_meshmap_presets(self):
        return { "name" : ExportPreset, "maps" : self.get_meshmaps() }

    def get_export_path(self):
        return self.output_path

    def get_parameters(self, is_convert=False, is_meshmap=False):
        export_format = ExportFormat
        export_path = self.get_export_path()
        if is_convert:
            export_format = ConvertFormat
            export_path = self.convert_path
        if is_meshmap:
            export_path = self.meshmap_path
            presets = self.get_export_meshmap_presets()
        else:
            presets = self.get_export_texture_presets()
        return {
            "exportPath"            : export_path,
            "exportShaderParams"    : ExportShaderParams,
            "defaultExportPreset"   : ExportPreset,
            "exportPresets"         : [ presets ],
            "exportList"            : self.get_export_list(),
            "exportParameters" : [
                {
                    "parameters" : {
                        "fileFormat" : export_format,
                        "dithering"  : True,
                        "sizeLog2"   : self.get_size(),
                        "paddingAlgorithm" : PaddingAlgorithm,
                        "dilationDistance" : DilationDistance
                    }
                }
            ]
        }

    def output_meshmap(self):
        output_parameters = self.get_parameters(False, True)
        spex.export_project_textures(output_parameters)

    def output_textures(self):
        if not self.valid:
            err("Project name is incorrect!")
            return None
        output_parameters = self.get_parameters(False, False)
        # Call substance painter API export
        try:
            texture_export_result = spex.export_project_textures(
                output_parameters
            )
        except ProjectError as error:
            pass
        except ValueError as error:
            pass
        else:
            status   = texture_export_result.status
            message  = texture_export_result.message
            textures = texture_export_result.textures
        if status == spex.ExportStatus.Success:
            if self.with_convert:
                convert_parameters = self.get_parameters(True, False)
                sources = spex.list_project_textures(output_parameters)[
                    (self.shader, "")
                ]
                targets = spex.list_project_textures(convert_parameters)[
                    (self.shader, "")
                ]
                successful_converted = self.convert(zip(sources, targets))
                print("Converted :\n" + "\n".join(successful_converted))
        elif status == spex.ExportStatus.Cancelled:
            log("Export process has been cancelled.")
        elif status == spex.ExportStatus.Warning:
            log(message)
        elif status == spex.ExportStatus.Error:
            err(message)

    def preview_output_textures(self):
        if not self.valid:
            err("Project name is incorrect!")
            return None
        output_parameters = self.get_parameters(False, False)
        for key, value in spex.list_project_textures(output_parameters).items():
            print(key)
            print("\nReady export :\n" + "\n".join(value))

    def create_directory(self, directory):
        if isdir(directory):
            # log("{0} is exists.".format(directory))
            return ""
        try:
            os.mkdir(directory)
        except FileExistsError as error:
            warn("The directory is exists : {0}".format(directory))
        except Exception as e:
            err("Can't create directory : {0}".format(directory))
            raise
        else:
            log("Created : {0}".format(directory))
        return directory

    def convert(self, convert_pairs=[]):
        convert_commands = []
        successful = []
        for source, destination in convert_pairs:
            if not isfile(source):
                warn("{0} is not found.".format(source))
                continue
            destination_directory = dirname(destination)
            try:
                self.create_directory(destination_directory)
            except:
                return []
            convert_commands.append([Converter, '-o', destination, source])
        if not convert_commands:
            warn("No images need to convert.")
            return []
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        for command in convert_commands:
            process = subprocess.Popen(command, startupinfo=startup_info)
            return_code = process.communicate()
            if not return_code:
                log('Converted : {0}'.format(command[2]))
            else:
                successful.append(command[2])
        return successful

class TextureSetWrapper(object):
    def __init__(self, texture_set):
        super().__init__()
        if isinstance(texture_set, str):
            self.texture_set = spts.TextureSet.from_name(texture_set)
        elif isinstance(texture_set, spts.TextureSet):
            self.texture_set = texture_set
        else:
            raise AssertionError(
                "TextureSetWrapper must create from string or TextureSet object"
            )
        self.channels = {}

    def get_channels(self):
        stack = spts.Stack.from_name(self.name())
        for k, v in spts.ChannelType.__members__.items():
            if stack.has_channel(v):
                channel = stack.get_channel(v)
                if k.startswith("User"):
                    self.channels[channel.label()] = channel
                else:
                    self.channels[k] = channel
        if __DEBUG__: print(self.channels)
        return self.channels

    def get_texture_name(self):
        workflow = Workflow()
        ts_name = self.texture_set.name()
        if ts_name.startswith('User'):
            ts_name = self.texture_set.label()
        title = workflow.get_title().replace('$textureSet', ts_name)
        if is_udim(ts_name):
            name = LegacyName
        else:
            name = ExportName.replace("$textureSet", ts_name)
        name = name.format(title, "(Channel)")
        return name

    def name(self):
        return self.texture_set.name()

class TextureExporterDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(__Title__ + " " + __Version__)
        if isfile(_IconImageFile):
            self.setWindowIcon(QtGui.QIcon(_IconImageFile))
        self.texture_set_check_boxes = []
        self.texture_sets = []
        self.convert_tx_commands = []
        self.is_convert_tx = False
        self.shader_name = ""
        self.workflow = Workflow()
        status = self.workflow.status()
        if status == Workflow.Successful:
            self.launch_UI()
        elif status == Workflow.NameIsNotCorrect:
            self.invalid_UI()
        else:
            self.no_projectUI()

    def texture_set_check_change(self, status):
        for check_box in self.texture_set_check_boxes:
            check_box.setChecked(status)

    def toggle_is_convert_tx(self, status):
        self.is_convert_tx = status

    def change_shader_name(self, name):
        self.shader_name = name

    def export_texture(self):
        scope_expression = ""
        is_convert = self.convert_cb.isChecked()
        is_force_8bits = self.force_8bits_cb.isChecked()
        all_texture_sets = [ts.name() for ts in spts.all_texture_sets()]
        for index, texture_set in enumerate(self.texture_sets):
            if texture_set not in all_texture_sets:
                warn("{0} is not found.".format(texture_set))
                continue
            check_box = self.texture_set_check_boxes[index]
            if not check_box.isChecked():
                log("Skip : {0}".format(texture_set))
                continue
            if self.switch_range_cb.isChecked():
                scope_expression = self.udim_range_le.text()
            exporter = Exporter(
                texture_set,
                self.shader_name,
                scope_expression,
                is_convert,
                is_force_8bits
            )
            exporter.output_textures()

    def explore_directory(self):
        directory = self.workflow.get_previous_directory().replace("/", "\\")
        subprocess.Popen(r'explorer /select, "{0}"'.format(directory))

    def export_mesh_map(self):
        radio = len(self.texture_sets) / 100;
        for index, texture_set in enumerate(self.texture_sets):
            check_box = self.texture_set_check_boxes[index]
            if not check_box.isChecked():
                log("Skip : {0}".format(texture_set))
                continue
            exporter = Exporter(texture_set)
            exporter.output_meshmap()

    def preview_export(self):
        all_texture_sets = [ts.name() for ts in spts.all_texture_sets()]
        scope_expression = ""
        if self.switch_range_cb.isChecked():
            scope_expression = self.udim_range_le.text()
        for index, texture_set in enumerate(self.texture_sets):
            exporter = Exporter(texture_set, self.shader_name, scope_expression)
            log("[Preview] {0}".format(texture_set))
            exporter.preview_output_textures()
        ExportChannelRangeKeeper.set("store1", scope_expression)

    def no_projectUI(self):
        """
            If project is not opened.
        """
        main_layout = QtWidgets.QVBoxLayout()
        info = QtWidgets.QLabel("No Project has been opened.")
        info.setStyleSheet(_GlobalLabelStyle)
        main_layout.addWidget(info)
        self.setLayout(main_layout)

    def invalid_UI(self):
        """
            If project name is incorrect.
        """
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(
            QtWidgets.QLabel(
                "Project Name is incorrect : %s" % self.workflow.name()
            )
        )
        self.setLayout(main_layout)

    def refresh_selections(self, parent_layout):
        texture_sets = spts.all_texture_sets()
        clean_layout(parent_layout)
        self.texture_sets.clear()
        self.texture_set_check_boxes.clear()
        for ts in [TextureSetWrapper(ts) for ts in spts.all_texture_sets()]:
            check_box = QtWidgets.QCheckBox(ts.name())
            check_box.setToolTip(ts.get_texture_name())
            self.texture_sets.append(ts.name())
            check_box.setChecked(False)
            self.texture_set_check_boxes.append(check_box)
            parent_layout.addWidget(check_box)

    def launch_UI(self):
        main_layout         = QtWidgets.QVBoxLayout()
        title_layout        = QtWidgets.QHBoxLayout()
        title_layout.setAlignment(QtCore.Qt.AlignLeft)
        config_name_label   = QtWidgets.QLabel("Project :" + ConfigName)
        config_name_label.setStyleSheet("font: bold 16px")
        title_layout.addWidget(config_name_label)
        main_layout.setAlignment(QtCore.Qt.AlignTop)
        main_layout.addLayout(title_layout)
        main_layout.addWidget(CxLd.ui.make_separator())
        selection_layout    = QtWidgets.QVBoxLayout()
        check_layout        = QtWidgets.QHBoxLayout()
        executable_layout   = QtWidgets.QVBoxLayout()
        # Check buttons ---------------------------------------------
        self.refresh_btn    = QtWidgets.QPushButton('Refresh')
        self.refresh_btn.setStyleSheet(_GlobalButtonStyle)
        self.check_all_btn  = QtWidgets.QPushButton('Check All')
        self.check_all_btn.setStyleSheet(_GlobalButtonStyle)
        self.uncheck_all_btn= QtWidgets.QPushButton('Uncheck All')
        self.uncheck_all_btn.setStyleSheet(_GlobalButtonStyle)
        check_layout.addWidget(self.refresh_btn)
        check_layout.addWidget(self.check_all_btn)
        check_layout.addWidget(self.uncheck_all_btn)
        # -----------------------------------------------------------
        # Scroll Layout and Area ------------------------------------
        ts_choice_title = QtWidgets.QLabel("TEXTURE SETS")
        ts_choice_title.setStyleSheet("font : bold 14px")
        selection_layout.addWidget(ts_choice_title)
        scroll_layout = QtWidgets.QVBoxLayout()
        scroll_layout.addLayout(check_layout)
        scroll_layout.addWidget(CxLd.ui.make_separator())
        scroll_layout.addLayout(selection_layout)
        scroll_layout.addWidget(CxLd.ui.make_separator())
        scroll_layout.setAlignment(QtCore.Qt.AlignTop)
        scroll_area         = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content      = QtWidgets.QWidget(scroll_area)
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        self.refresh_selections(selection_layout)
        main_layout.addWidget(scroll_area)
        # -----------------------------------------------------------
        # Range Input -----------------------------------------------
        udim_range_layout = QtWidgets.QHBoxLayout()
        self.switch_range_cb = QtWidgets.QCheckBox('Range')
        self.switch_range_cb.setCheckState(QtCore.Qt.Unchecked)
        self.switch_range_cb.setStyleSheet(_GlobalCheckBoxStyle)
        self.switch_range_cb.setToolTip(
            'If toggled, exporter will has range due expression.'
        )
        self.udim_range_le = QtWidgets.QLineEdit()
        self.udim_range_le.setEnabled(False)
        self.udim_range_le.setStyleSheet(_GlobalLineEditStyle)
        self.udim_range_le.setToolTip(
            'Channel:UdimStart-UdimEnd, "*" is wildcard set to all.'
        )
        self.udim_range_le.setText(ExportChannelRangeKeeper.get("store1"))
        # Completer
        completer = QtWidgets.QCompleter(list(ChannelMaps.keys()), self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.udim_range_le.setCompleter(completer)
        # main_layout.addWidget(CxLd.ui.make_separator())
        udim_range_layout.addWidget(self.switch_range_cb)
        udim_range_layout.addWidget(self.udim_range_le)
        main_layout.addLayout(udim_range_layout)
        # -----------------------------------------------------------
        options_layout = QtWidgets.QHBoxLayout()
        options_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.convert_cb         = QtWidgets.QCheckBox("Convert")
        self.convert_cb.setToolTip(Converter)
        if not Settings.converter_is_exists(): self.convert_cb.setEnabled(False)
        self.force_8bits_cb = QtWidgets.QCheckBox("Force 8bits")
        self.combined_meshmap_cb = QtWidgets.QCheckBox("Combined Meshmap")
        options_layout.addWidget(self.convert_cb)
        options_layout.addWidget(self.force_8bits_cb)
        options_layout.addWidget(self.combined_meshmap_cb)
        main_layout.addLayout(options_layout)
        # Executable buttons ----------------------------------------
        self.export_texture_btn = QtWidgets.QPushButton("Export Textures")
        self.export_texture_btn.setStyleSheet(_GlobalButtonStyle)
        self.export_meshmap_btn     = QtWidgets.QPushButton("Export Mesh Maps")
        self.export_meshmap_btn.setStyleSheet(_GlobalButtonStyle)
        self.explore_directory_btn  = QtWidgets.QPushButton("Explore Directory")
        self.explore_directory_btn.setStyleSheet(_GlobalButtonStyle)
        self.preview_export_btn = QtWidgets.QPushButton("Preview Textures")
        self.preview_export_btn.setStyleSheet(_GlobalButtonStyle)
        executable_layout.addWidget(CxLd.ui.make_separator())
        executable_layout.addWidget(self.export_texture_btn)
        executable_layout.addWidget(self.export_meshmap_btn)
        executable_layout.addWidget(self.explore_directory_btn)
        executable_layout.addWidget(self.preview_export_btn)
        main_layout.addLayout(executable_layout)
        # -----------------------------------------------------------
        # Connections -----------------------------------------------
        self.refresh_btn.clicked.connect(
            lambda : self.refresh_selections(selection_layout)
        )
        self.check_all_btn.clicked.connect(
            lambda : self.texture_set_check_change(True)
        )
        self.uncheck_all_btn.clicked.connect(
            lambda : self.texture_set_check_change(False)
        )
        self.switch_range_cb.stateChanged.connect(self.udim_range_le.setEnabled)
        self.export_texture_btn.clicked.connect(self.export_texture)
        self.export_meshmap_btn.clicked.connect(self.export_mesh_map)
        self.explore_directory_btn.clicked.connect(self.explore_directory)
        self.preview_export_btn.clicked.connect(self.preview_export)
        # -----------------------------------------------------------
        self.setLayout(main_layout)

def start_plugin():
    spev.DISPATCHER.connect(spev.ProjectOpened, refresh_ui)
    spev.DISPATCHER.connect(spev.ProjectCreated, refresh_ui)
    spev.DISPATCHER.connect(spev.ProjectAboutToClose, clean_ui)
    refresh_ui()

def close_plugin():
    spev.DISPATCHER.disconnect(spev.ProjectOpened, refresh_ui)
    spev.DISPATCHER.disconnect(spev.ProjectCreated, refresh_ui)
    spev.DISPATCHER.disconnect(spev.ProjectAboutToClose, clean_ui)
    clean_ui()

def refresh_ui(*args):
    clean_ui()
    texture_exporter_widget = TextureExporterDialog()
    spui.add_dock_widget(texture_exporter_widget)
    PluginWidgets.append(texture_exporter_widget)

def clean_ui(*args):
    for widget in PluginWidgets:
        spui.delete_ui_element(widget)
    PluginWidgets.clear()

if __name__ == '__main__':
    start_plugin()
