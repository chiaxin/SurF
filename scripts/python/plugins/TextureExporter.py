#
# TextureExporter
#
# Author : Chia Xin Lin ( nnnight@gmail.com )
#
# Version : 0.1.03 (beta)
#
# First Build : 2020/09/18
# Last Updated: 2020/10/26
#
# Substance Painter Version : 2020.2.0 (6.2.0)
#

from PySide2 import QtWidgets, QtGui, QtCore
from os.path import dirname, basename, join, isdir, isfile, realpath
import CxLd.ui
import CxLd.meta
from CxLd.utils import reverse_replace
import sys
import subprocess
import json
import os
import re
import tempfile
import substance_painter.ui         as spui
import substance_painter.event      as spev
import substance_painter.project    as sppj
import substance_painter.textureset as spts
import substance_painter.export     as spex
import substance_painter.logging    as splg

# -----------------------------------------
__Version__= '0.1.01 (beta)'
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
    "TextureExporterIcon.svg"
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
    border-width : 1px;
    border-radius: 2px;
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

_MakeTxOptions = " ".join([
    "-oiio",
    "-u",
    "--checknan",
    "--constant-color-detect",
    "--monochrome-detect",
    "--opaque-detect"
])

ExportChannelRangeKeeper = CxLd.meta.Metadata("te_Channel_Ranges")
ForceEightBitKeeper      = CxLd.meta.Metadata("te_Force_Eight_Bit")
ConvertAfterKeeper       = CxLd.meta.Metadata("te_Convert_After")
ColorCorrectKeeper       = CxLd.meta.Metadata("te_Color_Correct")
CombinedMeshMapKeeper    = CxLd.meta.Metadata("te_Combined_Meshmap")

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
    Python              = Settings.value("python")
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

_MultiProcessConvertScript = """
import subprocess
import multiprocessing
maketx = r"{0}"
def work(source, destination):
    process = subprocess.Popen('"%s" -oiio -o "%s" "%s"' % (
        maketx, destination, source
    ))

if __name__ == "__main__":
    workers = []
    for src, dest in targets:
        workers.append(multiprocessing.Process(
            target = work,
            args = (src, dest)
        ))
    for worker in workers:
        worker.start()
""".format(Converter)

_SRgbConvertOption = '--colorconvert sRGB "scene-linear Rec 709/sRGB"'

_MultiProcessConvertPoolScript = """
import subprocess
import multiprocessing
from os.path import basename
maketx = r"{0}"
def work(pairs):
    raw_process = '"%s" {1} -o "%s" "%s"'
    srgb_process= '"%s" {1} {2} -o "%s" "%s"'
    arguments = raw_process
    for channel in convert_channels:
        if pairs[0].find(channel) > 0:
            arguments = srgb_process
            break
    process = subprocess.Popen(arguments % (maketx, pairs[1], pairs[0]))
    process.communicate()

if __name__ == "__main__":
    cpu_count = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(cpu_count)
    pool.map(work, targets)
""".format(Converter, _MakeTxOptions, _SRgbConvertOption)

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
            err("The project name is incorrect : {0}".format(self.basename))
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
    SRgbConvertChannels = []
    def __init__(self, shader, shader_name="", parse="",
        with_convert=False, force_8_bits=False, is_combined=False,
        is_color_correct=False
    ):
        super().__init__()
        self.shader = shader
        self.shader_name = shader_name
        self.scope_map = {}
        self.with_convert = with_convert
        self.force_8_bits = force_8_bits
        self.is_color_correct = is_color_correct
        self.is_combined = is_combined
        self.texture_set = TextureSetWrapper(
            spts.TextureSet.from_name(self.shader)
        )
        self.channel_maps = self.texture_set.get_channels()
        if parse:
            self.scope_map = self.get_channel_udim_range(parse)
        self.output_path = self.get_output_directory()
        self.create_directory(self.output_path)
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
        unique_names = set()
        texture_set = self.texture_set
        for label, channel in self.channel_maps.items():
            if label.find("#") > 0:
                user_channel, label = label.split("#")
            src_map_type = "documentMap"
            if label.lower() not in ChannelMaps:
                warn("{0} not in channel lists".format(label))
                continue
            channel_name = ChannelMaps.get(label.lower(), None)
            if not channel_name:
                warn("Can't found channel label : %s" % label)
                continue
            elif channel_name in unique_names:
                warn("Duplicated channel name : %s" % channel_name)
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
            elif channel.label():
                src_map_name = user_channel
            channel_format = channel.format()
            indivduals = ('R', 'G', 'B')
            if str(channel_format).startswith('L'):
                indivduals = ('L')
            ch_describe = dict()
            ch_describe['fileName'] = self.get_export_name(channel_name)
            unique_names.add(channel_name)
            channels = []
            parameters = {}
            fmt_value = str(channel.format())
            if self.force_8_bits:
                parameters["bitDepth"] = "8"
            else:
                if fmt_value in bit_depth_8_list:
                    parameters["bitDepth"] = "8"
                elif fmt_value in bit_depth_16_list:
                    parameters["bitDepth"] = "16"
                elif fmt_value in bit_depth_32_list:
                    parameters["bitDepth"] = "32"
            if fmt_value == "ChannelFormat.sRGB8":
                Exporter.SRgbConvertChannels.append(channel_name)
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

    def get_export_list(self, is_meshmap=False):
        if is_meshmap:
            return [{ "rootPath" : self.shader }]
        export_list = []
        output_maps = []
        uv_tiles = []
        root_path = self.shader
        if self.scope_map:
            wildcard_range = self.scope_map.pop("*", [])
            for channel in list(self.scope_map):
                if channel not in ChannelMaps:
                    continue
                uv_tiles = self.scope_map.pop(channel, [])
                short = ChannelMaps[channel]
                export_list.append({
                    "rootPath" : root_path,
                    "filter" : {
                        "outputMaps" : [self.get_export_name(short)]
                    }
                })
                if uv_tiles:
                    export_list[-1]["filter"]["uvTiles"] = uv_tiles[:]
                elif wildcard_range:
                    export_list[-1]["filter"]["uvTiles"] = wildcard_range[:]
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
        range_maps = {}
        if not expression:
            return range_maps
        expressions = re.findall(parser, expression)
        if not expressions:
            return range_maps
        normalize_u = lambda udim: (udim - 1001) % 10
        normalize_v = lambda udim: (udim - 1001)// 10
        is_wildcard_setup = False
        all_range_buffers = []
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
            if is_wildcard_setup:
                all_range_buffers = udim_range_buffers
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
                    range_maps[channel] = all_range_buffers
        return range_maps

    def get_meshmaps(self):
        maps = []
        title = self.get_title()
        texture_set = TextureSetWrapper(spts.TextureSet.from_name(self.shader))
        if self.is_combined:
            ch_describe = dict()
            ch_describe["fileName"] = MeshMapName.format(title, "CombinedMap")
            channels = []
            channels.append({
                "destChannel" : "R",
                "srcChannel"  : "L",
                "srcMapType"  : "meshMap",
                "srcMapName"  : "ambient_occlusion"
            })
            channels.append({
                "destChannel" : "G",
                "srcChannel"  : "L",
                "srcMapType"  : "meshMap",
                "srcMapName"  : "curvature"
            })
            channels.append({
                "destChannel" : "B",
                "srcChannel"  : "L",
                "srcMapType"  : "meshMap",
                "srcMapName"  : "thickness"
            })
            ch_describe['channels'] = channels
            ch_describe['parameters'] = {
                "fileFormat" : ExportFormat,
                "bitDepth"   : "8"
            }
            maps.append(ch_describe)
        else:
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
                ch_describe['parameters'] = {
                    "fileFormat" : ExportFormat,
                    "bitDepth"   : "8"
                }
                maps.append(ch_describe)
        return maps

    def get_export_texture_presets(self):
        return { "name" : ExportPreset, "maps" : self.get_channel_maps() }

    def get_export_meshmap_presets(self):
        return { "name" : ExportPreset, "maps" : self.get_meshmaps()}

    def get_export_path(self):
        return self.output_path

    def get_parameters(self,
            is_convert=False,
            is_meshmap=False
        ):
        export_format = ExportFormat
        export_path = self.get_export_path()
        if is_convert:
            export_format = ConvertFormat
            export_path = self.convert_path
            self.create_directory(export_path)
        if is_meshmap:
            export_path = self.meshmap_path
            self.create_directory(export_path)
            presets = self.get_export_meshmap_presets()
        else:
            presets = self.get_export_texture_presets()
        return {
            "exportPath"            : export_path,
            "exportShaderParams"    : ExportShaderParams,
            "defaultExportPreset"   : ExportPreset,
            "exportPresets"         : [ presets ],
            "exportList"            : self.get_export_list(is_meshmap),
            "exportParameters" : [
                {
                    "parameters" : {
                        "fileFormat" : export_format,
                        "dithering"  : Dithering,
                        "sizeLog2"   : self.get_size(),
                        "paddingAlgorithm" : PaddingAlgorithm,
                        "dilationDistance" : DilationDistance
                    }
                }
            ]
        }

    def output_meshmap(self, is_combined=False):
        output_parameters = self.get_parameters(False, True, is_combined)
        spex.export_project_textures(output_parameters)

    def output_textures(self):
        Exporter.SRgbConvertChannels.clear()
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
            textures = texture_export_result.textures[(self.shader, "")]
        if status == spex.ExportStatus.Success:
            if self.with_convert:
                sources = [img.replace("\\", "/") for img in textures]
                convert_pairs = [
                    (img, join(
                        reverse_replace(
                            dirname(img), ExportDirectory, ConvertDirectory, 1
                        ),
                        reverse_replace(
                            basename(img), ExportFormat, ConvertFormat, 1
                        )
                    ).replace("\\", "/")
                    ) for img in sources
                ]
                self.multiprocess_convert(convert_pairs)
        elif status == spex.ExportStatus.Cancelled:
            log("Export process has been cancelled.")
        elif status == spex.ExportStatus.Warning:
            warn(message)
        elif status == spex.ExportStatus.Error:
            err(message)

    def preview_output_textures(self):
        if not self.valid:
            err("Project name is incorrect!")
            return None
        output_parameters = self.get_parameters(False, False)
        for key, value in spex.list_project_textures(output_parameters).items():
            if value:
                log("\nTexture Set - %s :\n" % key[0] + "\n".join(value))
            else:
                log("\nTexture Set - %s : Nothing\n" % key[0])

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

    def write_multiprocess_script(self, convert_pairs=[]):
        script = join(tempfile.gettempdir(), "_subpainter_mp_convert.py")
        length = len(convert_pairs) - 1
        line_counter = 0
        try:
            with open(script, "w") as fh:
                #if self.is_color_correct:
                if True:
                    buffer = ""
                    for channel in Exporter.SRgbConvertChannels:
                        buffer = '"' + channel + '", '
                    fh.write("convert_channels = [{0}]\n".format(buffer))
                else:
                    fh.write("convert_channels = []\n")
                fh.write("targets = [\n")
                for src, dest in convert_pairs:
                    self.create_directory(dirname(dest))
                    if line_counter == length:
                        fh.write('\t("%s", "%s")\n]\n' % (src, dest))
                    else:
                        fh.write('\t("%s", "%s"),\n' % (src, dest))
                    line_counter = line_counter + 1
                # fh.write(_MultiProcessConvertScript)
                fh.write(_MultiProcessConvertPoolScript)
        except Exception as e:
            print(e)
            warn("Failed to write script : {0}".format(script))
        return '\"' + script.replace("\\", "/") + '\"'

    def multiprocess_convert(self, convert_pairs=[]):
        py_script = self.write_multiprocess_script(convert_pairs)
        process = subprocess.Popen(py_script, shell=True)
        return_code = process.wait()
        if return_code == 0:
            log("Convert successful.")
        else:
            warn("Convert error occurred.")

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
        """
        Members : BaseColor, Height, Specular, Opacity, Emmissive,
                  Displacement, Glossiness, Roughness, AnisotropyLevel,
                  Anisotropyangle, Transmissive, Reflection, Ior, Metallic,
                  Normal, AO, Diffuse, Specularlevel, BlendingMask,
                  Scattering, and User0 - User7
        If the channel type is User[0-7], its key will User[0-7]#Label,
        for example : User0 - mask01 = User0#mask01
        """
        stack = spts.Stack.from_name(self.name())
        for name, channel_type in spts.ChannelType.__members__.items():
            if stack.has_channel(channel_type):
                channel = stack.get_channel(channel_type)
                if name.startswith("User"):
                    self.channels[name.lower()+"#"+channel.label()] = channel
                else:
                    self.channels[name.lower()] = channel
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

    def store_metadata(self):
        ExportChannelRangeKeeper.set("store", self.udim_range_le.text())
        ForceEightBitKeeper.set("boolean", self.force_8bits_cb.isChecked())
        ConvertAfterKeeper.set("boolean", self.convert_cb.isChecked())
        ColorCorrectKeeper.set("boolean", self.color_correct_cb.isChecked())

    def reset_metadata(self):
        self.udim_range_le.setText(ExportChannelRangeKeeper.get("store"))
        if ForceEightBitKeeper.get("boolean"):
            self.force_8bits_cb.setChecked(True)
        else:
            self.force_8bits_cb.setChecked(False)
        if ConvertAfterKeeper.get("boolean"):
            self.convert_cb.setChecked(True)
        else:
            self.convert_cb.setChecked(False)
        if ColorCorrectKeeper.get("boolean"):
            self.color_correct_cb.setChecked(True)
        else:
            self.color_correct_cb.setChecked(False)
        if CombinedMeshMapKeeper.get("boolean"):
            self.combined_meshmap_cb.setChecked(True)
        else:
            self.combined_meshmap_cb.setChecked(False)

    def export_texture(self):
        scope_expression = ""
        is_convert = self.convert_cb.isChecked()
        is_force_8bits = self.force_8bits_cb.isChecked()
        is_color_correct = self.color_correct_cb.isChecked()
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
                is_force_8bits,
                is_color_correct
            )
            exporter.output_textures()
        self.store_metadata()

    def explore_directory(self):
        directory = self.workflow.get_previous_directory().replace("/", "\\")
        subprocess.Popen(r'explorer /select, "{0}"'.format(directory))

    def export_mesh_map(self):
        for index, texture_set in enumerate(self.texture_sets):
            check_box = self.texture_set_check_boxes[index]
            if not check_box.isChecked():
                log("Skip : {0}".format(texture_set))
                continue
            exporter = Exporter(texture_set)
            exporter.output_meshmap(self.combined_meshmap_cb.isChecked())

    def preview_export(self):
        all_texture_sets = [ts.name() for ts in spts.all_texture_sets()]
        scope_expression = ""
        if self.switch_range_cb.isChecked():
            scope_expression = self.udim_range_le.text()
        for index, texture_set in enumerate(all_texture_sets):
            exporter = Exporter(texture_set, self.shader_name, scope_expression)
            exporter.preview_output_textures()

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
        info_label = QtWidgets.QLabel(
            "Project Name incorrect : %s\n%s" % (
                self.workflow.name(),
                ProjectNameMatcher
            )
        )
        info_label.setStyleSheet(_GlobalLabelStyle)
        main_layout.addWidget(info_label)
        self.setLayout(main_layout)

    def refresh_selections(self, parent_layout):
        texture_sets = spts.all_texture_sets()
        clean_layout(parent_layout)
        self.texture_sets.clear()
        self.texture_set_check_boxes.clear()
        for ts in [TextureSetWrapper(ts) for ts in spts.all_texture_sets()]:
            name = ts.name()
            check_box = QtWidgets.QCheckBox(name)
            check_box.setToolTip(ts.get_texture_name())
            self.texture_sets.append(ts.name())
            check_box.setChecked(False)
            self.texture_set_check_boxes.append(check_box)
            parent_layout.addWidget(check_box)

    def launch_UI(self):
        main_layout         = QtWidgets.QVBoxLayout()
        title_layout        = QtWidgets.QHBoxLayout()
        title_layout.setAlignment(QtCore.Qt.AlignLeft)
        config_name_label   = QtWidgets.QLabel(ConfigName)
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
        self.udim_range_le.setText(ExportChannelRangeKeeper.get("store"))
        # Completer
        completer = QtWidgets.QCompleter(list(ChannelMaps.keys()), self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.udim_range_le.setCompleter(completer)
        # main_layout.addWidget(CxLd.ui.make_separator())
        main_layout.addWidget(CxLd.ui.make_separator())
        main_layout.addWidget(QtWidgets.QLabel("COMPONENT"))
        udim_range_layout.addWidget(self.switch_range_cb)
        udim_range_layout.addWidget(self.udim_range_le)
        main_layout.addLayout(udim_range_layout)
        # -----------------------------------------------------------
        format_layout  = QtWidgets.QHBoxLayout()
        format_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.convert_cb         = QtWidgets.QCheckBox("Convert")
        self.convert_cb.setToolTip(Converter)
        if not Settings.converter_is_exists(): self.convert_cb.setEnabled(False)
        self.force_8bits_cb = QtWidgets.QCheckBox("Force 8bits")
        self.color_correct_cb = QtWidgets.QCheckBox("Color Correct")
        self.combined_meshmap_cb = QtWidgets.QCheckBox("Combined Meshmap")
        main_layout.addWidget(CxLd.ui.make_separator())
        main_layout.addWidget(QtWidgets.QLabel("FORMATS"))
        format_layout.addWidget(self.force_8bits_cb)
        format_layout.addWidget(self.convert_cb)
        format_layout.addWidget(self.color_correct_cb)
        format_layout.addWidget(self.combined_meshmap_cb)
        main_layout.addLayout(format_layout)
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
        # -----------------------------------------------------------
        self.reset_metadata()

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
