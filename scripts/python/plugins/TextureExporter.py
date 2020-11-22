#
# TextureExporter
#
# Author : Chia Xin Lin ( nnnight@gmail.com )
#
# Version : 0.1.10 (beta)
#
# First Build : 2020/09/18
# Last Updated: 2020/11/21
#
# Substance Painter Version : 2020.2.0 (6.2.0)
#

from PySide2 import QtWidgets, QtGui, QtCore
from typing import List, Dict, Tuple, Set, Union, Type, cast
from os.path import dirname, basename, join, isdir, isfile, realpath
import SurF.ui
import SurF.meta
from SurF.utils import reverse_replace, log, warn, err
import subprocess
import json
import os
import re
import tempfile
import substance_painter.ui as spui
import substance_painter.event as spev
import substance_painter.export as spex
import substance_painter.project as sppj
import substance_painter.exception as sper
import substance_painter.textureset as spts

# -----------------------------------------
__Version__ = '0.1.10 (beta)'
__Author__ = "Chia Xin Lin"
__Email__ = "nnnight@gmail.com"
__Contact__ = "https://github.com/chiaxin"
__Title__ = 'Texture Exporter'
# -----------------------------------------

PluginWidgets: List[QtWidgets.QWidget] = []

_ExportConfigFile: str = "ExportConfig.json"

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

_MeshMaps: List[str] = [
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

ExportChannelRangeKeeper = SurF.meta.Metadata("te_Channel_Ranges")
ForceEightBitKeeper = SurF.meta.Metadata("te_Force_Eight_Bit")
ConvertAfterKeeper = SurF.meta.Metadata("te_Convert_After")
ColorCorrectKeeper = SurF.meta.Metadata("te_Color_Correct")
CombinedMeshMapKeeper = SurF.meta.Metadata("te_Combined_Meshmap")


def is_udim(name: str):
    return re.match(r"^[1-9]\d{3}$", name)


def get_script_path() -> str:
    return dirname(realpath(__file__))


class ExportSettingNoFoundError(Exception):
    def __init__(self, message):
        self._message = message

    def __repr__(self):
        return self._message


class ExportSettingError(Exception):
    pass


class ExportConfig(object):
    Limits: Dict[str, list] = {
        "output_size": [512, 1024, 2048, 8192, 4096],
        "export_format": ["png", "tga", "jpg", "tif"],
        "normal_map": ["directx", "open_gl"],
        "color_correct": [0, 1],
        "export_shader_params": [0, 1],
        "dithering": [0, 1],
        "padding_algorithm": [
            "passthrough", "color", "transparent", "diffusion", "infinite"
        ]
    }

    def __init__(self) -> None:
        self.settings: dict = {}
        config_file: str = join(get_script_path(), _ExportConfigFile)
        if isfile(config_file):
            with open(config_file, 'r') as file_handle:
                try:
                    data = json.load(file_handle)
                except Exception as unknown_error:
                    err(str(unknown_error))
                    raise
                else:
                    self.settings = data
        else:
            message: str = f"Can't get export config file : {config_file}"
            err(message)
            raise ExportSettingNoFoundError(message)

    @staticmethod
    def is_executable(file) -> bool:
        return isfile(file) and os.access(file, os.X_OK)

    def value(self, key: str):
        if key not in self.settings:
            raise ExportSettingNoFoundError(f"Failed to get setting : {key}")
        value = self.settings[key]
        if key in ExportConfig.Limits.keys():
            if value not in ExportConfig.Limits[key]:
                value = ExportConfig.Limits[key][-1]
        return value

    def converter_is_exists(self) -> bool:
        return self.is_executable(self.value("converter"))


Converter: str = ""


try:
    Settings: ExportConfig = ExportConfig()
    ProjectNameMatcher = re.compile(Settings.value("naming"))
    Python = Settings.value("python")
    ConfigName = Settings.value("configName")
    Converter = Settings.value("converter")
    ExportName = Settings.value("export_name")
    LegacyName = Settings.value("legacy_name")
    MeshMapName = Settings.value("meshmap_name")
    ExportDirectory = Settings.value("export_path")
    ConvertDirectory = Settings.value("convert_path")
    MeshMapDirectory = Settings.value("meshmap_path")
    MeshMapSettings = Settings.value("meshmaps")
    OutputSize = Settings.value("output_size")
    ExportFormat = Settings.value("export_format")
    ConvertFormat = Settings.value("convert_format")
    ChannelMaps = Settings.value("maps")
    NormalMapFormat = Settings.value("normal_map")
    ExportPreset = Settings.value("preset")
    ExportShaderParams = Settings.value("export_shader_params") == 1
    Dithering = Settings.value("dithering") == 1
    DilationDistance = Settings.value("dilationDistance")
    PaddingAlgorithm = Settings.value("paddingAlgorithm")
    Color_Correct: bool = Settings.value("color_correct") == 1
    Is_Combined_Mesh_Maps: bool = Settings.value(
        "meshmaps")["settings"]["combined"] == 1
except ExportSettingNoFoundError as e:
    err(str(e))

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
    """
    Core class to communicate with substance painter project.
    """
    Successful = 0
    NameIsNotCorrect = 1
    ProjectNotOpened = 2

    def __init__(self):
        self.title = ""
        if sppj.is_open():
            self.project: str = sppj.file_path()
            self.basename: str = basename(self.project)
            self.valid: bool = True
        else:
            self.project: str = ""
            self.basename: str = ""
            self.valid: bool = False
        matcher = ProjectNameMatcher.match(self.basename)
        if matcher:
            self.title: str = matcher.group(1)
            self.valid: bool = True
        else:
            err(f"The project name is incorrect : {self.basename}")
            self.valid = False

    def name(self) -> str:
        return self.basename

    def get_title(self) -> str:
        return self.title

    def status(self) -> int:
        """
        If project is opened and name is matched, return 0 (Successful).
        Opened but name is not matched, return 1 (Name is not correct).
        Project is not opened, return 2 (Project not opened).
        :return:
        Integer : status
        """
        if sppj.is_open() and self.valid:
            return Workflow.Successful
        elif sppj.is_open():
            return Workflow.NameIsNotCorrect
        else:
            return Workflow.ProjectNotOpened

    def get_previous_directory(self) -> str:
        """
        Get the root directory due the project path.
        for example :
            Project : D:/working/texture/sub/ABC_Asset_SpA_v001.spp
                ==> D:/working/texture
            Project : D:/projects/substance/texture/sub/ABC_Asset_SpA_v001.spp
                ==> D:/projects/substance/texture
        :return:
            str : The root directory.
            * If no project opened, It will return empty string.
        """
        if self.project:
            return dirname(dirname(self.project)).replace("\\", "/")
        return ""

    def get_output_directory(self) -> str:
        """
        Get the output directory due the project path.
        for example :
            * Our output path is "TIF"
            Project : D:/working/texture/sub/ABC_Asset_SpA_v001.spp
                ==> D:/working/texture/TIF
            Project : D:/projects/substance/texture/sub/ABC_Asset_SpA_v001.spp
                ==> D:/projects/substance/texture/TIF
        :return:
            str : The output directory.
            * If no project opened, It will return empty string.
        """
        prev_directory: str = self.get_previous_directory()
        if "ExportDirectory" in globals() and prev_directory:
            return join(prev_directory, ExportDirectory).replace('\\', '/')
        return ""

    def get_convert_directory(self) -> str:
        """
        Get the convert directory due the project path.
        for example :
            * Our convert path is "TX"
            Project : D:/working/texture/sub/ABC_Asset_SpA_v001.spp
                ==> D:/working/texture/TX
            Project : D:/projects/substance/texture/sub/ABC_Asset_SpA_v001.spp
                ==> D:/projects/substance/texture/TX
        :return:
            str : The convert directory.
            * If no project opened, It will return empty string.
        """
        prev_directory: str = self.get_previous_directory()
        if "ConvertDirectory" in globals() and prev_directory:
            return join(prev_directory, ConvertDirectory).replace("\\", "/")
        return ""

    def get_meshmap_directory(self) -> str:
        prev_directory: str = self.get_previous_directory()
        if "MeshMapDirectory" in globals() and prev_directory:
            return join(prev_directory, MeshMapDirectory).replace("\\", "/")
        return ""


class ExportSettings(object):
    """
    Maintain export settings
    How to use :
        export_setting = ExportSettings()
        export_setting.convert = True
        export_setting.force8bits = True
        export_setting.combined = False
        export_setting.color_correct = False
        export_setting.get()
        => Get {
            "with_convert" : True,
            "is_force_8bits" : True,
            "is_combined" : False,
            "is_color_correct" : False
        }
    """

    def __init__(self) -> None:
        self.with_convert: bool = False
        self.is_force_8bits: bool = False
        self.is_combined: bool = False
        self.is_color_correct: bool = False
        self.is_mesh_map: bool = False
        self.scope: str = ""

    @property
    def convert(self) -> bool:
        return self.with_convert

    @convert.setter
    def convert(self, toggle: bool) -> None:
        self.with_convert = toggle

    @property
    def force8bits(self) -> bool:
        return self.is_force_8bits

    @force8bits.setter
    def force8bits(self, toggle: bool) -> None:
        self.is_force_8bits = toggle

    @property
    def combined(self) -> bool:
        return self.is_combined

    @combined.setter
    def combined(self, toggle: bool) -> None:
        self.is_combined = toggle

    @property
    def color_correct(self) -> bool:
        return self.is_color_correct

    @color_correct.setter
    def color_correct(self, toggle: bool) -> None:
        self.is_color_correct = toggle

    @property
    def mesh_map(self) -> bool:
        return self.is_mesh_map

    @mesh_map.setter
    def mesh_map(self, toggle: bool) -> None:
        self.is_mesh_map = toggle

    def set_scope_map(self, _scope: str) -> None:
        self.scope = _scope

    def get_scope_map(self) -> str:
        return self.scope

    def get(self) -> Dict[str, bool]:
        """
        :return:
            Dict[str, bool] Setting maps.
        """
        return {
            "with_convert": self.convert,
            "is_force_8bits": self.force8bits,
            "is_combined": self.combined,
            "is_color_correct": self.color_correct
        }


class TextureSetWrapper(object):
    def __init__(self, texture_set: Union[spts.TextureSet, str]) -> None:
        if isinstance(texture_set, str):
            try:
                self.texture_set = spts.TextureSet.from_name(texture_set)
            except sper.ProjectError as project_error:
                err(str(project_error))
                raise NotImplemented
            except sper.ServiceNotFoundError as service_not_found_error:
                err(str(service_not_found_error))
                raise NotImplemented
            except ValueError as value_error:
                err(str(value_error))
                raise NotImplemented
            except Exception as unknown_error:
                err(str(unknown_error))
                raise
        elif isinstance(texture_set, spts.TextureSet):
            self.texture_set = texture_set
        else:
            raise AssertionError(
                "TextureSetWrapper must create from string or TextureSet object"
            )
        self.channels: Dict[str, spts.Channel] = self.get_channels()

    def get_channels(self) -> Dict[str, spts.Channel]:
        """
        Members : BaseColor, Height, Specular, Opacity, Emmissive,
                  Displacement, Glossiness, Roughness, AnisotropyLevel,
                  Anisotropyangle, Transmissive, Reflection, Ior, Metallic,
                  Normal, AO, Diffuse, Specularlevel, BlendingMask,
                  Scattering, and User0 - User7
        If the channel type is User[0-7], its key will User[0-7]#Label,
        for example : User0 - mask01 = User0#mask01
        """
        channels: Dict[str, spts.Channel] = {}
        try:
            stack: spts.Stack = spts.Stack.from_name(self.name)
        except sper.ProjectError as project_error:
            err(str(project_error))
            raise NotImplemented
        except sper.ServiceNotFoundError as service_not_found_error:
            err(str(service_not_found_error))
            raise NotImplemented
        except ValueError as value_error:
            err(str(value_error))
            raise NotImplemented
        name: str
        channel_type: spts.ChannelType
        for name, channel_type in spts.ChannelType.__members__.items():
            if stack.has_channel(channel_type):
                channel: spts.Channel = stack.get_channel(channel_type)
                channel_key: str = name.lower() + "#" + channel.label() \
                    if name.startswith("User") else name.lower()
                channels.setdefault(channel_key, channel)
        return channels

    def get_output_name(self) -> str:
        workflow: Workflow = Workflow()
        texture_set_name: str = self.name
        title: str = workflow.get_title().replace('$textureSet', texture_set_name)
        name = LegacyName if is_udim(texture_set_name) \
            else ExportName.replace("$textureSet", texture_set_name)
        full_name: str = name.format(title, "(CHANNEL)")
        return full_name

    @property
    def name(self) -> str:
        return self.texture_set.name()

    @name.setter
    def name(self, _name) -> None:
        """
        Do not set texture set's name.
        """
        raise NotImplemented

    @staticmethod
    def all_texture_set() -> List[str]:
        return [texture_set.name() for texture_set in spts.all_texture_sets()]


class Exporter(Workflow):
    def __init__(
            self, shader: TextureSetWrapper, _settings: ExportSettings
    ) -> None:
        super().__init__()
        self.settings: ExportSettings = _settings
        self.need_color_correct_channels: List[str] = []
        self.texture_set: TextureSetWrapper = shader
        self.channel_maps = self.texture_set.get_channels()
        self.output_path: str = self.get_output_directory()
        self.convert_path: str = self.get_convert_directory()
        self.mesh_map_path: str = self.get_meshmap_directory()
        self.create_directory(self.output_path)

    def get_title(self) -> str:
        """
        :return:
            The export title, if texture set name is Udim, get title + _$textureSet.
        """
        title: str = self.title + "_$textureSet" if is_udim(self.texture_set.name) else self.title
        return title

    def get_export_name(self, ch: str) -> str:
        """
        :param ch:
            The channel's name, for example : Color, Bump, Normal...
        :return:
            The full export name,
            If title or export name is empty return empty string.
        """
        title: str = self.get_title()
        export_n: str = LegacyName if is_udim(self.texture_set.name) else ExportName
        full_name: str = export_n.format(title, ch) if title and export_n else ""
        return full_name

    def get_channel_maps(self) -> list:
        """
        :return:
            Get export channel maps.
        """
        channel_maps: list = []
        unique_names: Set[str] = set()
        bit_depth_8_list: Tuple[str, str, str] = (
            "ChannelFormat.sRGB8", "ChannelFormat.L8", "ChannelFormat.RGB8"
        )
        bit_depth_16_list: Tuple[str, str, str, str] = (
            "ChannelFormat.L16", "ChannelFormat.RGB16", "ChannelFormat.L16F",
            "ChannelFormat.RGB16F"
        )
        bit_depth_32_list: Tuple[str, str] = (
            "ChannelFormat.L32F", "ChannelFormat.RGB32F"
        )
        for label, channel in self.channel_maps.items():
            user_channel: str = ""
            if label.find("#") > 0:
                user_channel, label = label.split("#")
            if label.lower() not in ChannelMaps:
                warn(f"{label} not in channel lists")
                continue
            channel_name: str = ChannelMaps.get(label.lower(), "")
            if not channel_name:
                warn(f"Can't found channel label : {label}")
                continue
            if channel_name in unique_names:
                warn(f"Duplicated channel name : {channel_name}")
                continue
            src_map_name: str = label.lower()
            src_map_type: str = "virtualMap" if src_map_name == "normal" else "documentMap"
            if src_map_name == "normal":
                src_map_name = ("Normal_OpenGL", "Normal_DirectX")[NormalMapFormat == "open_gl"]
            src_map_name = user_channel if channel.label() else src_map_name
            channel_format: str = channel.format()
            elements: tuple = ("L",) if str(channel_format).startswith("L") else ("R", "G", "B")
            ch_describe: dict = dict()
            ch_describe['fileName'] = self.get_export_name(channel_name)
            unique_names.add(channel_name)
            channels: List[Dict[str, str]] = []
            parameters: dict = dict()
            fmt_value: str = str(channel.format())
            if self.settings.force8bits:
                parameters["bitDepth"] = "8"
            else:
                if fmt_value in bit_depth_8_list:
                    parameters["bitDepth"] = "8"
                elif fmt_value in bit_depth_16_list:
                    parameters["bitDepth"] = "16"
                elif fmt_value in bit_depth_32_list:
                    parameters["bitDepth"] = "32"
            if fmt_value == "ChannelFormat.sRGB8":
                self.need_color_correct_channels.append(label)
            for component in elements:
                channels.append({
                    "destChannel": component,
                    "srcChannel": component,
                    "srcMapType": src_map_type,
                    "srcMapName": src_map_name
                })
            ch_describe['channels'] = channels
            ch_describe['parameters'] = parameters
            channel_maps.append(ch_describe)
        return channel_maps

    def get_export_list(self) -> List[dict]:
        export_list: List[dict] = []
        scope: str = self.settings.get_scope_map()
        if scope:
            scope_map: Dict[str, list] = self.get_scope(scope)
            wildcard_range = scope_map.pop("*", [])
            for channel in list(scope_map):
                if channel not in ChannelMaps:
                    continue
                uv_tiles: List[int] = scope_map.pop(channel, [])
                short_name: str = ChannelMaps[channel]
                export_list.append({
                    "rootPath": self.texture_set.name,
                    "filter": {
                        "outputMaps": [self.get_export_name(short_name)]
                    }
                })
                if uv_tiles:
                    export_list[-1]["filter"][""] = uv_tiles[:]
                elif wildcard_range:
                    export_list[-1]["filter"]["uvTiles"] = wildcard_range[:]
        else:
            export_list = [{"rootPath": self.texture_set.name}]
        return export_list

    @staticmethod
    def get_size() -> int:
        return {
            4096: 12,
            2048: 11,
            1024: 10,
            512: 9
        }.get(OutputSize, 2048)

    def get_scope(self, expression: str) -> Dict[str, list]:
        def normalize_u(num: int) -> int:
            return (num - 1001) % 10

        def normalize_v(num: int) -> int:
            return (num - 1001) // 10

        def normalize(num: int) -> List[int]:
            return [normalize_u(num), normalize_v(num)]

        range_maps: Dict[str, list] = {}
        if not expression:
            return range_maps
        channel_expression: str = r"(\*|\w[\w\d]+)"
        num_expression: str = r"(\*|(?:[1-9]\d{3})(?:-[1-9]\d{3})?)"
        parser: str = f"{channel_expression}:{num_expression}"
        expressions: List[Tuple[str, str]] = re.findall(parser, expression)
        is_wildcard_setup: bool = False
        all_range_buffers: List[int] = []
        channel: str
        numbers: str
        for channel, numbers in expressions:
            if channel == "*":
                is_wildcard_setup = True
            elif channel not in ChannelMaps.keys():
                warn(f"The channel is not in list : {channel}")
                continue
            number_range_buffers: List[List[int, int]] = []
            if is_wildcard_setup:
                all_range_buffers: List[List[int, int]] = number_range_buffers
            if re.match(r"[1-9]\d{3}-[1-9]\d{3}", numbers):
                start, end = [int(from_to) for from_to in numbers.split("-")]
                if end <= start:
                    warn(f"Invalid UDIM range : {start}-{end}")
                    continue
                numbers: List[int] = list(range(start, end + 1))
                number_range_buffers: List[List[int, int]] = [
                    [normalize_u(num), normalize_v(num)] for num in numbers
                ]
            elif re.match(r"[1-9]\d{3}", numbers):
                number: int = int(numbers)
                number_range_buffers = [normalize(number)]
            # A wildcard matched : diffuse:*
            elif numbers == "*":
                number_range_buffers = []
            else:
                warn(f"Invalid range expression : {numbers}")
            if channel in range_maps:
                range_maps[channel].extend(number_range_buffers)
            else:
                range_maps[channel] = number_range_buffers[:]
        if is_wildcard_setup:
            for channel in self.channel_maps:
                if channel not in range_maps:
                    range_maps[channel] = all_range_buffers
        return range_maps

    def get_mesh_maps(self) -> List[dict]:
        maps: List[dict] = []
        title: str = self.get_title()
        # Combined mesh map
        if self.settings.combined:
            ch_describe: dict = dict()
            ch_describe["fileName"] = MeshMapName.format(title, "CombinedMap")
            ch_describe["channels"] = [{
                "destChannel": "R",
                "srcChannel": "L",
                "srcMapType": "meshMap",
                "srcMapName": "ambient_occlusion"
            }, {
                "destChannel": "G",
                "srcChannel": "L",
                "srcMapType": "meshMap",
                "srcMapName": "curvature"
            }, {
                "destChannel": "B",
                "srcChannel": "L",
                "srcMapType": "meshMap",
                "srcMapName": "thickness"
            }]
            ch_describe['parameters'] = dict(fileFormat=ExportFormat, bitDepth="8")
            maps.append(ch_describe)
        # Not combined mesh map
        else:
            for mesh_map in _MeshMaps:
                ch_describe: dict = dict()
                ch_describe["fileName"] = MeshMapName.format(title, mesh_map)
                channels: List[dict] = []
                for ch in ["R", "G", "B"]:
                    channel_description = {
                        "destChannel": ch,
                        "srcChannel": ch,
                        "srcMapType": "meshMap",
                        "srcMapName": mesh_map
                    }
                    channels.append(channel_description)
                ch_describe["channels"] = channels
                ch_describe['parameters'] = dict(fileFormat=ExportFormat, bitDepth="8")
                maps.append(ch_describe)
        return maps

    def get_export_texture_presets(self) -> dict:
        return {"name": ExportPreset, "maps": self.get_channel_maps()}

    def get_export_mesh_map_presets(self) -> dict:
        return {"name": ExportPreset, "maps": self.get_mesh_maps()}

    def get_export_path(self) -> str:
        return self.output_path

    def get_parameters(self) -> dict:
        export_format = ExportFormat
        export_path = self.get_export_path()
        if self.settings.convert:
            export_format: str = ConvertFormat
            export_path: str = self.convert_path
            self.create_directory(export_path)
        if self.settings.mesh_map:
            export_path: str = self.mesh_map_path
            self.create_directory(export_path)
            presets = self.get_export_mesh_map_presets()
        else:
            presets = self.get_export_texture_presets()
        return {
            "exportPath": export_path,
            "exportShaderParams": ExportShaderParams,
            "defaultExportPreset": ExportPreset,
            "exportPresets": [presets],
            "exportList": self.get_export_list(),
            "exportParameters": [{
                "parameters": {
                    "fileFormat": export_format,
                    "dithering": Dithering,
                    "sizeLog2": self.get_size(),
                    "paddingAlgorithm": PaddingAlgorithm,
                    "dilationDistance": DilationDistance
                }
            }]
        }

    def output_mesh_map(self):
        output_parameters = self.get_parameters()
        spex.export_project_textures(output_parameters)

    def output_textures(self) -> spex.ExportStatus:
        self.need_color_correct_channels.clear()
        if not self.valid:
            err("Project name is incorrect!")
            return None
        output_parameters = self.get_parameters()
        export_result = spex.export_project_textures(output_parameters)
        status: spex.ExportStatus = export_result.status
        message: str = export_result.message
        textures: List[str] = export_result.textures[(self.texture_set.name, "")]
        assert isinstance(status, spex.ExportStatus)
        if status == spex.ExportStatus.Success:
            if self.settings.convert:
                sources: List[str] = [texture.replace("\\", "/") for texture in textures]
                self.multiprocess_convert(
                    [(image, join(
                        reverse_replace(
                            dirname(image),
                            ExportDirectory,
                            ConvertDirectory,
                            1
                        ),
                        reverse_replace(
                            basename(image),
                            ExportFormat,
                            ConvertFormat,
                            1
                        )
                    ).replace("\\", "/")) for image in sources
                     ]
                )
        elif status == spex.ExportStatus.Cancelled:
            log("Export process has been cancelled.")
        elif status == spex.ExportStatus.Warning:
            warn(message)
        elif status == spex.ExportStatus.Error:
            err(message)
        return status

    def preview_output_textures(self) -> int:
        if not self.valid:
            err("Project name is incorrect!")
            return 0
        output_parameters: dict = self.get_parameters()
        output_textures: dict = spex.list_project_textures(output_parameters)
        texture_set: Tuple[str, str]
        textures: list
        for texture_set, textures in output_textures:
            if textures:
                log("Texture Set : {0}:\n{1}".format(texture_set[0], "\n".join(textures)))
        return len(output_textures)

    @staticmethod
    def create_directory(directory: str) -> str:
        if isdir(directory):
            return ""
        try:
            os.mkdir(directory)
        except FileExistsError as file_exists_error:
            warn(f"The directory is exists : {file_exists_error}")
            raise
        except Exception as unknown_error:
            err(f"Can't create directory : {unknown_error}")
            raise
        else:
            log(f"Created : {directory}")
        return directory

    def convert(self, convert_pairs: List[Tuple[str, str]]) -> List[str]:
        convert_commands: List[list] = []
        successful: List[str] = []
        source: str
        destination: str
        for source, destination in convert_pairs:
            if not isfile(source):
                warn(f"{source} is not found.")
                continue
            destination_directory: str = dirname(destination)
            try:
                self.create_directory(destination_directory)
            except FileExistsError as file_exists_error:
                err(str(file_exists_error))
                return []
            except Exception as unknown_error:
                err(str(unknown_error))
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

    def write_multiprocess_script(self, convert_pairs):
        script: str = join(tempfile.gettempdir(), "substance_painter_mp.py")
        length: int = len(convert_pairs) - 1
        line_counter: int = 0
        try:
            with open(script, "w") as fh:
                if self.settings.color_correct:
                    buffer: str = ""
                    channel: str
                    for channel in self.need_color_correct_channels:
                        buffer = '"' + channel + '", '
                    fh.write(f"convert_channels = [{buffer}]\n")
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
                fh.write(_MultiProcessConvertPoolScript)
        except Exception as unknown_error:
            warn(str(unknown_error))
            warn("Failed to write script : {0}".format(script))
        return '\"' + script.replace("\\", "/") + '\"'

    def multiprocess_convert(self, convert_pairs: List[Tuple[str, str]]) -> int:
        py_script = self.write_multiprocess_script(convert_pairs)
        process = subprocess.Popen(py_script, shell=True)
        return_code = process.wait()
        if return_code == 0:
            log("Convert successful.")
        else:
            warn("Convert error occurred.")
        return return_code


class TextureExporterDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview_export_btn = QtWidgets.QPushButton("Preview Textures")
        self.explore_directory_btn = QtWidgets.QPushButton("Explore Directory")
        self.export_mesh_map_btn = QtWidgets.QPushButton("Export Mesh Maps")
        self.export_texture_btn = QtWidgets.QPushButton("Export Textures")
        self.force_8bits_cb = QtWidgets.QCheckBox("Force 8bits")
        self.convert_cb: QtWidgets.QCheckBox = QtWidgets.QCheckBox("Convert")
        self.limited_range_le = QtWidgets.QLineEdit()
        self.switch_range_cb = QtWidgets.QCheckBox('Range')
        # Layouts
        self.selections_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        # Buttons
        self.uncheck_all_btn = QtWidgets.QPushButton('Uncheck All')
        self.check_all_btn = QtWidgets.QPushButton('Check All')
        self.refresh_btn = QtWidgets.QPushButton('Refresh')
        # Styles
        self.export_texture_btn.setStyleSheet(_GlobalButtonStyle)
        self.export_mesh_map_btn.setStyleSheet(_GlobalButtonStyle)
        self.explore_directory_btn.setStyleSheet(_GlobalButtonStyle)
        self.preview_export_btn.setStyleSheet(_GlobalButtonStyle)
        self.refresh_btn.setStyleSheet(_GlobalButtonStyle)
        self.check_all_btn.setStyleSheet(_GlobalButtonStyle)
        self.uncheck_all_btn.setStyleSheet(_GlobalButtonStyle)
        # --------------------------------------------------------------------
        self.setWindowTitle(__Title__ + " " + __Version__)
        if isfile(_IconImageFile):
            self.setWindowIcon(QtGui.QIcon(_IconImageFile))
        ts_bind_type = Dict[TextureSetWrapper, QtWidgets.QCheckBox]
        self.texture_set_binds: ts_bind_type = {}
        self.convert_tx_commands: List[str] = []
        self.is_convert_tx: bool = False
        self.shader_name: str = ""
        self.workflow: Workflow = Workflow()
        status: int = self.workflow.status()
        (   # Launch window
            self.launch_main_window,
            self.launch_invalid_window,
            self.launch_no_project_window
        )[status]()

    def texture_set_check_change(self, status: bool) -> None:
        check_box: QtWidgets.QCheckBox
        for check_box in self.texture_set_binds.values():
            assert not isinstance(check_box, QtWidgets.QCheckBox)
            check_box.setChecked(status)

    def store_metadata(self) -> None:
        ExportChannelRangeKeeper.set("store", self.limited_range_le.text())
        ForceEightBitKeeper.set("boolean", self.force_8bits_cb.isChecked())
        ConvertAfterKeeper.set("boolean", self.convert_cb.isChecked())

    def reset_metadata(self) -> None:
        self.limited_range_le.setText(ExportChannelRangeKeeper.get("store"))
        if ForceEightBitKeeper.get("boolean"):
            self.force_8bits_cb.setChecked(True)
        else:
            self.force_8bits_cb.setChecked(False)
        if ConvertAfterKeeper.get("boolean"):
            self.convert_cb.setChecked(True)
        else:
            self.convert_cb.setChecked(False)

    def get_settings(self) -> ExportSettings:
        """
        :return:
            ExportSettings object
        """
        settings: ExportSettings = ExportSettings()
        settings.convert = self.convert_cb.isChecked()
        settings.force8bits = self.convert_cb.isChecked()
        settings.color_correct = Color_Correct
        settings.combined = Is_Combined_Mesh_Maps
        if self.switch_range_cb.isChecked():
            settings.set_scope_map(self.limited_range_le.text())
        return settings

    def export_texture(self) -> None:
        """
        Export texture function, and saving metadata after export.
        """
        texture_set: TextureSetWrapper
        settings: ExportSettings = self.get_settings()
        all_texture_sets: List[str] = TextureSetWrapper.all_texture_set()
        for texture_set, ui in self.texture_set_binds.items():
            if ui.isChecked() and texture_set.name in all_texture_sets:
                exporter = Exporter(texture_set, settings)
                exporter.output_textures()
        self.store_metadata()

    def export_mesh_map(self) -> None:
        """
        Export mesh map function.
        :return:
        """
        texture_set: TextureSetWrapper
        settings: ExportSettings = self.get_settings()
        ui: QtWidgets.QCheckBox
        for texture_set, ui in self.texture_set_binds.items():
            if ui.isChecked():
                exporter = Exporter(texture_set, settings)
                exporter.output_mesh_map()

    def explore_directory(self) -> None:
        """
        Explore the output directory.
        """
        directory: str = self.workflow.get_previous_directory()
        directory = directory.replace("\\", "/")
        subprocess.Popen(f'explorer /select, "{directory}"')

    def preview_export(self) -> None:
        """
        Print the all texture ready to export.
        """
        texture_set: TextureSetWrapper
        all_texture_sets = TextureSetWrapper.all_texture_set()
        for texture_set, ui in self.texture_set_binds.items():
            if ui.isChecked() and texture_set.name in all_texture_sets:
                exporter = Exporter(texture_set,  self.get_settings())
                exporter.preview_output_textures()

    def refresh_selections(self) -> None:
        """
        Refresh all texture set list and QCheckBox selections.
        """
        def get_all() -> List[str]:
            return TextureSetWrapper.all_texture_set()

        def wrapper(texture_set) -> TextureSetWrapper:
            return TextureSetWrapper(texture_set)
        SurF.ui.clean_layout(self.selections_layout)
        self.texture_set_binds.clear()
        for texture_set_wrapper in [wrapper(ts) for ts in get_all()]:
            name: str = texture_set_wrapper.name
            check_box: QtWidgets.QCheckBox = QtWidgets.QCheckBox(name)
            self.texture_set_binds[texture_set_wrapper] = check_box
            check_box.setToolTip(texture_set_wrapper.get_output_name())
            check_box.setChecked(False)
            self.selections_layout.addWidget(check_box)

    def launch_no_project_window(self) -> None:
        """
        If project is not opened.
        """
        main_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        info: QtWidgets.QLabel = QtWidgets.QLabel("No Project has been opened")
        info.setStyleSheet(_GlobalLabelStyle)
        main_layout.addWidget(info)
        self.setLayout(main_layout)

    def launch_invalid_window(self) -> None:
        """
        If project name is incorrect.
        """
        main_layout: QtWidgets = QtWidgets.QVBoxLayout()
        info_label: QtWidgets.QLabel = QtWidgets.QLabel(
            "Project Name incorrect : {0}\n{1}".format(
                self.workflow.name(), ProjectNameMatcher
            )
        )
        info_label.setStyleSheet(_GlobalLabelStyle)
        main_layout.addWidget(info_label)
        self.setLayout(main_layout)

    def launch_main_window(self):
        def check_all():
            check_box: QtWidgets.QCheckBox
            for check_box in self.texture_set_binds.values():
                check_box.setChecked(True)

        def check_none():
            check_box: QtWidgets.QCheckBox
            for check_box in self.texture_set_binds.values():
                check_box.setChecked(False)

        def _add_line(layout: QtWidgets.QLayout) -> None:
            layout.addWidget(SurF.ui.make_separator())

        def _get_layout(_typ: str, _align: str = "") -> QtWidgets.QLayout:
            """
            :param _typ: "", "H", "V"
            :param _align:  "", "t", "b", "l", "r"
            :return:
                QLayout object
            """
            layout_symbol: str = _typ
            align_symbol: str = _align
            layout_build: Type[QtWidgets.QLayout] = {
                "": QtWidgets.QLayout,
                "H": QtWidgets.QHBoxLayout,
                "V": QtWidgets.QVBoxLayout
            }[layout_symbol]
            alignment: QtCore.Qt.Alignment = {
                "": None,
                "t": QtCore.Qt.AlignTop,
                "b": QtCore.Qt.AlignBottom,
                "l": QtCore.Qt.AlignLeft,
                "r": QtCore.Qt.AlignRight
            }[align_symbol]
            layout = layout_build()
            if alignment:
                layout.setAlignment(alignment)
            return cast(QtWidgets.QLayout, layout)
        main_layout = _get_layout("V", "t")
        title_layout = _get_layout("H", "l")
        check_layout = _get_layout("H")
        executable_layout = _get_layout("V")
        config_name_label = QtWidgets.QLabel(ConfigName)
        config_name_label.setStyleSheet("font: bold 16px")
        title_layout.addWidget(config_name_label)
        main_layout.addLayout(title_layout)
        _add_line(main_layout)
        # Add Buttons --------------------------------------------------------
        check_layout.addWidget(self.refresh_btn)
        check_layout.addWidget(self.check_all_btn)
        check_layout.addWidget(self.uncheck_all_btn)
        # --------------------------------------------------------------------
        # Scroll Layout and Area ---------------------------------------------
        scroll_layout = _get_layout("V", "t")
        scroll_layout.addLayout(check_layout)
        _add_line(scroll_layout)
        scroll_layout.addLayout(self.selections_layout)
        _add_line(scroll_layout)
        scroll_area: QtWidgets.QScrollArea = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content: QtWidgets.QWidget = QtWidgets.QWidget(scroll_area)
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        self.refresh_selections()
        main_layout.addWidget(scroll_area)
        # -----------------------------------------------------------
        # Range Input -----------------------------------------------
        limited_range_layout = QtWidgets.QHBoxLayout()
        self.switch_range_cb.setCheckState(QtCore.Qt.Unchecked)
        self.switch_range_cb.setStyleSheet(_GlobalCheckBoxStyle)
        self.switch_range_cb.setToolTip("Set limited range when exporting.")
        self.limited_range_le.setEnabled(False)
        self.limited_range_le.setStyleSheet(_GlobalLineEditStyle)
        self.limited_range_le.setToolTip(
            "Channel:Start-End, \"*\" is wildcard set for all."
        )
        self.limited_range_le.setText(ExportChannelRangeKeeper.get("store"))
        completer = QtWidgets.QCompleter(list(ChannelMaps.keys()), self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.limited_range_le.setCompleter(completer)
        _add_line(main_layout)
        main_layout.addWidget(QtWidgets.QLabel("COMPONENT"))
        limited_range_layout.addWidget(self.switch_range_cb)
        limited_range_layout.addWidget(self.limited_range_le)
        main_layout.addLayout(limited_range_layout)
        # -----------------------------------------------------------
        format_layout = QtWidgets.QHBoxLayout()
        format_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.convert_cb.setToolTip(Converter)
        if not Settings.converter_is_exists():
            self.convert_cb.setEnabled(False)
        _add_line(main_layout)
        main_layout.addWidget(QtWidgets.QLabel("FORMATS"))
        format_layout.addWidget(self.force_8bits_cb)
        format_layout.addWidget(self.convert_cb)
        main_layout.addLayout(format_layout)
        # Executable buttons ----------------------------------------
        _add_line(executable_layout)
        executable_layout.addWidget(self.export_texture_btn)
        executable_layout.addWidget(self.export_mesh_map_btn)
        executable_layout.addWidget(self.explore_directory_btn)
        executable_layout.addWidget(self.preview_export_btn)
        main_layout.addLayout(executable_layout)
        # -----------------------------------------------------------
        # Connections -----------------------------------------------
        self.refresh_btn.clicked.connect(self.refresh_selections)
        self.check_all_btn.clicked.connect(check_all)
        self.uncheck_all_btn.clicked.connect(check_none)
        self.switch_range_cb.stateChanged.connect(self.limited_range_le.setEnabled)
        self.export_texture_btn.clicked.connect(self.export_texture)
        self.export_mesh_map_btn.clicked.connect(self.export_mesh_map)
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


def refresh_ui():
    clean_ui()
    texture_exporter_widget = TextureExporterDialog()
    spui.add_dock_widget(texture_exporter_widget)
    PluginWidgets.append(texture_exporter_widget)


def clean_ui():
    for widget in PluginWidgets:
        spui.delete_ui_element(widget)
    PluginWidgets.clear()


if __name__ == '__main__':
    start_plugin()
