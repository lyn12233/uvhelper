# from . import uvstrap

import xml.etree.ElementTree as ET
from typing import Self, MutableSequence, Literal
import copy
from warnings import warn
import glob
from collections import OrderedDict
import os


class UVConfigBase(ET.Element):
    default_opts: dict[str, str]
    valid_keys: dict[str, None]
    option_keys: dict[str, None]
    options: OrderedDict[str, str]
    subconfigs: list["UVConfigBase"]

    def __init__(self, elem: ET.Element | str = "") -> None:
        if isinstance(elem, ET.Element):
            # copy
            super().__init__(elem.tag, elem.attrib)
            for sube in elem:
                self.append(sube)
        else:
            assert isinstance(elem, str)
            warn(f"creating empty config <{elem}/>")
            super().__init__(elem)
        self.default_opts = dict()
        self.valid_keys = dict()
        self.option_keys = dict()
        self.options = OrderedDict()
        self.subconfigs = []

    # make xml fits to key requirements
    def load_keys(self: Self):
        # update keys and validate
        self.option_keys.update(dict.fromkeys(self.default_opts))
        self.valid_keys.update(self.option_keys)
        for key in self.valid_keys:
            assert key.isidentifier(), f"invalid key {key} in {self.tag}"
        # remove invalid keys and collect existing keys
        subs: set[str] = set()
        for elem in self:
            if not elem.tag in self.valid_keys:
                warn(f"{elem.tag} is not a valid tag in {self.tag}")
                self.remove(elem)
            else:
                subs.add(elem.tag)
        # create keys that are options but do not exist
        for tag in set(self.default_opts) - subs:
            sube = ET.Element(tag)
            sube.text = self.default_opts[tag]
            warn(
                f"adding default elem <{tag}>{self.default_opts[tag]}<{tag}/> in {self.tag}"
            )
            self.append(sube)

    # load self.options from xml
    def load_options(self: Self):
        for key in self.option_keys:
            elem: ET.Element | None = self.find(f"./{key}")
            if elem is None:
                warn(f"expected option <{key}>...<{key}/>")
                self.options[key] = (
                    self.default_opts[key] if key in self.default_opts else ""
                )
            else:
                self.options[key] = elem.text if isinstance(elem.text, str) else ""

    def load(self: Self):
        self.load_keys()
        self.load_options()

    def sync_options(self: Self, recurse: bool = True):
        for key, val in self.options.items():
            assert key.isidentifier()
            elem: ET.Element | None = self.find(f"./{key}")
            if elem is None:
                warn(f"adding missing option <{key}>...<{key}/>")
                elem = UVConfigBase(key)
                self.append(elem)
            elem.text = "" if val is None else val
        if recurse:
            for sube in self.subconfigs:
                sube.sync_options(recurse)

    def link(self: Self, recurse: bool = True):
        # Remove existing children that match subconfig tags
        subconfig_tags = {sub.tag: i for i, sub in enumerate(self.subconfigs)}
        for i in range(len(self)):
            if self[i].tag in subconfig_tags:
                self[i] = self.subconfigs[subconfig_tags[self[i].tag]]
        if recurse:
            for sube in self.subconfigs:
                if not sube in self:
                    self.append(sube)
                sube.link(recurse)

    def __repr__(self, indent: int = 0, has_this: bool = True) -> str:
        rep = " " * indent + f"<{self.tag}>\n" if has_this else ""
        # for sube in self:
        # if isinstance(sube, UVConfigBase):
        # assert isinstance(sube, UVConfigBase)
        # rep += sube.__repr__(indent + 2)
        # else:
        # rep += " " * (indent + 2) + f"<{sube.tag}>{sube.text}</{sube.tag}>\n"
        for key, val in self.options.items():
            rep += " " * (indent + 2) + f"<{key}>{''if val is None else val}</{key}>\n"
        for sube in self.subconfigs:
            assert isinstance(sube, UVConfigBase)
            rep += sube.__repr__(indent + 2)
        rep += " " * indent + f"</{self.tag}>\n" if has_this else ""
        return rep


class UVTargetCommonOption(UVConfigBase):
    class TargetStatus(UVConfigBase):
        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "TargetStatus")
            assert self.tag == "TargetStatus", f"target status xml tag {self.tag}"

            self.default_opts = {
                "Error": "0",
                "ExitCodeStop": "0",
                "ButtonStop": "0",
                "NotGenerated": "0",
                "InvalidFlash": "1",
            }
            self.option_keys = dict.fromkeys(self.default_opts)
            self.valid_keys = self.option_keys

            self.load()

    target_status: TargetStatus

    class CostumeCommands(UVConfigBase):
        def __init__(
            self, elem: ET.Element | None = None, id: str = "U", default_tag: str = ""
        ) -> None:
            super().__init__(elem if elem is not None else default_tag)
            assert self.tag == default_tag, f"costume command xml tag {self.tag}"

            self.default_opts = {
                "RunUserProg1": "0",
                "RunUserProg2": "0",
                "UserProg1Name": "",
                "UserProg2Name": "",
                "UserProg1Dos16Mode": "0",
                "UserProg2Dos16Mode": "0",
                f"nStop{id}1X": "0",
                f"nStop{id}2X": "0",
            }
            self.option_keys = dict.fromkeys(self.default_opts)
            self.valid_keys = self.option_keys

            self.load()

    before_compile: CostumeCommands
    before_make: CostumeCommands
    after_make: CostumeCommands

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "TargetCommonOption")
        assert self.tag == "TargetCommonOption", f"common option xml tag {self.tag}"

        self.default_opts = {
            "Device": "STM32F103ZE",
            "Vendor": "STMicroelectronics",
            "PackID": "Keil.STM32F1xx_DFP.2.4.1",
            "PackURL": "https://www.keil.com/pack/",
            "Cpu": (
                'IRAM(0x20000000,0x00010000) IROM(0x08000000,0x00080000) CPUTYPE("Cortex-M3") CLOCK(12000000) ELITTLE'
            ),
            "FlashUtilSpec": "",
            "StartupFile": "",
            "FlashDriverDll": (
                "UL2CM3(-S0 -C0 -P0 -FD20000000 -FC1000 -FN1 -FF0STM32F10x_512 -FS08000000 -FL080000 -FP0($$Device:STM32F103ZE$Flash\\STM32F10x_512.FLM))"
            ),
            "DeviceId": "0",
            "RegisterFile": ("$$Device:STM32F103ZE$Device\\Include\\stm32f10x.h"),
            "MemoryEnv": "",
            "Cmp": "",
            "Asm": "",
            "Linker": "",
            "OHString": "",
            "InfinionOptionDll": "",
            "SLE66CMisc": "",
            "SLE66AMisc": "",
            "SLE66LinkerMisc": "",
            "SFDFile": "$$Device:STM32F103ZE$SVD\\STM32F103xx.svd",
            "bCustSvd": "0",
            "UseEnv": "0",
            "BinPath": "",
            "IncludePath": "",
            "LibPath": "",
            "RegisterFilePath": "",
            "DBRegisterFilePath": "",
            # target status
            "OutputDirectory": ".\\Objects\\",
            "OutputName": "",  # needs to be set later
            "CreateExecutable": "1",
            "CreateLib": "0",
            "CreateHexFile": "1",
            "DebugInformation": "1",
            "BrowseInformation": "1",
            "ListingPath": ".\\Listings\\",
            "HexFormatSelection": "1",
            "Merge32K": "0",
            "CreateBatchFile": "0",
            # before compile, before make, after make
            "SelectedForBatchBuild": "0",
            "SVCSIdString": "",
        }
        self.option_keys = dict.fromkeys(self.default_opts) | {"OutputName": None}
        self.valid_keys = self.option_keys | dict.fromkeys(
            (
                "TargetStatus",
                "BeforeCompile",
                "BeforeMake",
                "AfterMake",
            )
        )

        self.load()

        self.target_status = UVTargetCommonOption.TargetStatus(
            self.find("./TargetStatus")
        )
        self.before_compile = UVTargetCommonOption.CostumeCommands(
            self.find("./BeforeCompile"), "U", "BeforeCompile"
        )
        self.before_make = UVTargetCommonOption.CostumeCommands(
            self.find("./BeforeMake"), "B", "BeforeMake"
        )
        self.after_make = UVTargetCommonOption.CostumeCommands(
            self.find("./AfterMake"), "A", "AfterMake"
        )
        self.subconfigs = [
            self.target_status,
            self.before_compile,
            self.before_make,
            self.after_make,
        ]


class UVCommonProperty(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "CommonProperty")
        assert self.tag == "CommonProperty", f"common property xml tag {self.tag}"

        self.default_opts = {
            "UseCPPCompiler": "0",
            "RVCTCodeConst": "0",
            "RVCTZI": "0",
            "RVCTOtherData": "0",
            "ModuleSelection": "0",
            "IncludeInBuild": "1",
            "AlwaysBuild": "0",
            "GenerateAssemblyFile": "0",
            "AssembleAssemblyFile": "0",
            "PublicsOnly": "0",
            "StopOnExitCode": "3",
            "CustomArgument": "",
            "IncludeLibraryModules": "",
            "ComprImg": "1",
        }
        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys

        self.load()


class UVDllOption(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "DllOption")
        assert self.tag == "DllOption", f"DllOption tag {self.tag}"

        self.default_opts = {
            "SimDllName": "SARMCM3.DLL",
            "SimDllArguments": "-REMAP",
            "SimDlgDll": "DCM.DLL",
            "SimDlgDllArguments": "",
            "TargetDllName": "SARMCM3.DLL",
            "TargetDllArguments": "",
            "TargetDlgDll": "TCM.DLL",
            "TargetDlgDllArguments": "-pCM3",
        }
        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys

        self.load()


class UVDebugOption(UVConfigBase):
    class OPTHX(UVConfigBase):
        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "OPTHX")
            assert self.tag == "OPTHX", f"OPTHX tag {self.tag}"

            self.default_opts = {
                "HexSelection": "1",
                "HexRangeLowAddress": "0",
                "HexRangeHighAddress": "0",
                "HexOffset": "0",
                "Oh166RecLen": "16",
            }
            self.option_keys = dict.fromkeys(self.default_opts)
            self.valid_keys = self.option_keys

            self.load()

    opthx: OPTHX

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "DebugOption")
        assert self.tag == "DebugOption", f"DebugOption tag {self.tag}"

        self.valid_keys = {"OPTHX": None}

        self.opthx = UVDebugOption.OPTHX(self.find("./OPTHX"))

        self.subconfigs = [self.opthx]


class UVUtilities(UVConfigBase):
    class Flash1(UVConfigBase):
        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "Flash1")
            assert self.tag == "Flash1", f"Flash1 tag {self.tag}"

            self.default_opts = {
                "UseTargetDll": "1",
                "UseExternalTool": "0",
                "RunIndependent": "0",
                "UpdateFlashBeforeDebugging": "1",
                "Capability": "1",
                "DriverSelection": "4101",
            }
            self.option_keys = dict.fromkeys(self.default_opts)
            self.valid_keys = self.option_keys

            self.load()

    flash1: Flash1

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Utilities")
        assert self.tag == "Utilities", f"Utilities tag {self.tag}"

        self.default_opts = {
            "bUseTDR": "1",
            "Flash2": "BIN\\UL2CM3.DLL",
            "Flash3": "",
            "Flash4": "",
            "pFcarmOut": "",
            "pFcarmGrp": "",
            "pFcArmRoot": "",
            "FcArmLst": "0",
        }

        self.option_keys = dict.fromkeys(self.default_opts)

        self.valid_keys = self.option_keys | {"Flash1": None}

        self.load()

        self.flash1 = UVUtilities.Flash1(self.find("./Flash1"))

        self.subconfigs = [self.flash1]


class UVArmAdsMisc(UVConfigBase):
    class OnChipMemories(UVConfigBase):
        class Memory(UVConfigBase):
            def __init__(self, elem: ET.Element | None = None, tag: str = ""):
                super().__init__(elem if elem is not None else tag)
                assert self.tag == tag, f"memory xml tag {self.tag}"

                self.default_opts = {
                    "Type": "0",
                    "StartAddress": "0x0",
                    "Size": "0x0",
                }
                self.option_keys = dict.fromkeys(self.default_opts)
                self.valid_keys = self.option_keys

                self.load()

        ocms: list[Memory]
        iram: Memory
        irom: Memory
        xram: Memory
        ocr_rvct: list[Memory]  # represent vector

        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "OnChipMemories")
            assert self.tag == "OnChipMemories", f"on chip memories xml tag {self.tag}"

            self.ocms, self.rams, self.ocr_rvct = [], [], []
            for i in range(1, 7):
                self.ocms.append(
                    UVArmAdsMisc.OnChipMemories.Memory(
                        self.find(f"./Ocm{i}"), f"Ocm{i}"
                    )
                )

            self.iram = UVArmAdsMisc.OnChipMemories.Memory(
                self.find(f"./IRAM"), f"IRAM"
            )
            self.irom = UVArmAdsMisc.OnChipMemories.Memory(
                self.find(f"./IROM"), f"IROM"
            )
            self.xram = UVArmAdsMisc.OnChipMemories.Memory(
                self.find(f"./XRAM"), f"XRAM"
            )

            for i in range(1, 11):
                self.ocr_rvct.append(
                    UVArmAdsMisc.OnChipMemories.Memory(
                        self.find(f"./OCR_RVCT{i}"), f"OCR_RVCT{i}"
                    )
                )
            self.subconfigs = [
                s
                for s in (self.ocms + [self.iram, self.irom, self.xram] + self.ocr_rvct)
            ]

    on_chip_memories: OnChipMemories

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "ArmAdsMisc")
        assert self.tag == "ArmAdsMisc", f"target arm ads xml tag {self.tag}"

        self.default_opts = {
            "GenerateListings": "0",
            "asHll": "1",
            "asAsm": "1",
            "asMacX": "1",
            "asSyms": "1",
            "asFals": "1",
            "asDbgD": "1",
            "asForm": "1",
            "ldLst": "0",
            "ldmm": "1",
            "ldXref": "1",
            "BigEnd": "0",
            "AdsALst": "1",
            "AdsACrf": "1",
            "AdsANop": "0",
            "AdsANot": "0",
            "AdsLLst": "1",
            "AdsLmap": "1",
            "AdsLcgr": "1",
            "AdsLsym": "1",
            "AdsLszi": "1",
            "AdsLtoi": "1",
            "AdsLsun": "1",
            "AdsLven": "1",
            "AdsLsxf": "1",
            "RvctClst": "0",
            "GenPPlst": "0",
            "AdsCpuType": '"Cortex-M3"',
            "RvctDeviceName": "",
            "mOS": "0",
            "uocRom": "0",
            "uocRam": "0",
            "hadIROM": "1",
            "hadIRAM": "1",
            "hadXRAM": "0",
            "uocXRam": "0",
            "RvdsVP": "0",
            "RvdsMve": "0",
            "RvdsCdeCp": "0",
            "nBranchProt": "0",
            "hadIRAM2": "0",
            "hadIROM2": "0",
            "StupSel": "8",
            "useUlib": "0",
            "EndSel": "0",
            "uLtcg": "0",
            "nSecure": "0",
            "RoSelD": "3",
            "RwSelD": "3",
            "CodeSel": "0",
            "OptFeed": "0",
            "NoZi1": "0",
            "NoZi2": "0",
            "NoZi3": "0",
            "NoZi4": "0",
            "NoZi5": "0",
            "Ro1Chk": "0",
            "Ro2Chk": "0",
            "Ro3Chk": "0",
            "Ir1Chk": "1",
            "Ir2Chk": "0",
            "Ra1Chk": "0",
            "Ra2Chk": "0",
            "Ra3Chk": "0",
            "Im1Chk": "1",
            "Im2Chk": "0",
            "RvctStartVector": "",
        }
        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys | {"OnChipMemories": None}

        self.load()

        self.on_chip_memories = UVArmAdsMisc.OnChipMemories(
            self.find("./OnChipMemories")
        )
        self.subconfigs = [self.on_chip_memories]


class UVVariousControls(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "VariousControls")
        assert self.tag == "VariousControls", f"various controls xml tag {self.tag}"

        self.default_opts = {
            "MiscControls": "",
            "Define": "",
            "Undefine": "",
            "IncludePath": "",
        }
        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys

        self.load()


class UVCads(UVConfigBase):  # compiler arm developer suite
    various_controls: UVVariousControls

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Cads")
        assert self.tag == "Cads", f"cads xml tag {self.tag}"

        self.default_opts = {
            "interw": "1",
            "Optim": "1",
            "oTime": "0",
            "SplitLS": "0",
            "OneElfS": "1",
            "Strict": "0",
            "EnumInt": "0",
            "PlainCh": "0",
            "Ropi": "0",
            "Rwpi": "0",
            "wLevel": "2",
            "uThumb": "0",
            "uSurpInc": "0",
            "uC99": "1",
            "uGnu": "1",
            "useXO": "0",
            "v6Lang": "5",
            "v6LangP": "3",
            "vShortEn": "1",
            "vShortWch": "1",
            "v6Lto": "0",
            "v6WtE": "0",
            "v6Rtti": "0",
        }

        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys | {"VariousControls": None}

        self.load()

        self.various_controls = UVVariousControls(self.find("./VariousControls"))
        self.subconfigs = [self.various_controls]


class UVAads(UVConfigBase):  # assembler arm developer suite
    various_controls: UVVariousControls

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Aads")
        assert self.tag == "Aads", f"aads xml tag {self.tag}"

        self.default_opts = {
            "interw": "1",
            "Ropi": "0",
            "Rwpi": "0",
            "thumb": "0",
            "SplitLS": "0",
            "SwStkChk": "0",
            "NoWarn": "0",
            "uSurpInc": "0",
            "useXO": "0",
            "ClangAsOpt": "1",
        }

        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys | {"VariousControls": None}

        self.load()

        self.various_controls = UVVariousControls(self.find("./VariousControls"))
        self.subconfigs = [self.various_controls]


class UVLDads(UVConfigBase):  # linker arm developer suite
    various_controls: UVVariousControls

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "LDads")
        assert self.tag == "LDads", f"lads xml tag {self.tag}"

        self.default_opts = {
            "umfTarg": "1",
            "Ropi": "0",
            "Rwpi": "0",
            "noStLib": "0",
            "RepFail": "1",
            "useFile": "0",
            "TextAddressRange": "0x08000000",
            "DataAddressRange": "0x20000000",
            "pXoBase": "",
            "ScatterFile": "",
            "IncludeLibs": "",
            "IncludeLibsPath": "",
            "Misc": "",
            "LinkerInputFile": "",
            "DisabledWarnings": "",
        }

        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys

        self.load()


class UVGroup(UVConfigBase):

    class Files(UVConfigBase):
        class File(UVConfigBase):
            def __init__(self, elem: ET.Element | None = None) -> None:
                super().__init__(elem if elem is not None else "File")
                assert self.tag == "File", f"file xml tag {self.tag}"

                self.option_keys = dict.fromkeys(("FileName", "FileType", "FilePath"))
                self.valid_keys = self.option_keys

                self.load()

            @property
            def path(self) -> str:
                return self.options["FilePath"]

            @path.setter
            def path(self, val: str):
                assert isinstance(val, str) and not os.path.isabs(
                    val
                ), f"file invalid path {val}"
                self.options["FilePath"] = val
                self.options["FileName"] = os.path.basename(val)
                # needs amendment
                self.options["FileType"] = "1" if val.endswith(".c") else "2"

        files: list[File]

        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "Files")
            assert self.tag == "Files"

            self.valid_keys = {"File": None}

            self.files = []
            for elem in self.iterfind("./File"):
                self.files.append(UVGroup.Files.File(elem))
            self.subconfigs = [f for f in self.files]

        def add_file(self, fn: str):
            f = UVGroup.Files.File()
            f.path = fn
            self.files.append(f)
            self.subconfigs.append(f)

    files: Files

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Group")
        assert self.tag == "Group", f"group xml tag {self.tag}"

        self.default_opts = {"GroupName": "DefaultGroupName"}
        self.option_keys = {"GroupName": None}
        self.valid_keys = self.option_keys | {"Files": None}

        self.load()

        self.files = UVGroup.Files(self.find("./Files"))
        self.subconfigs = [self.files]

    @property
    def name(self) -> str:
        return self.options["GroupName"]

    @name.setter
    def name(self, val: str):
        assert isinstance(val, str) and val.isidentifier(), f"invalid group name {val}"
        self.options["GroupName"] = val


class UVTarget(UVConfigBase):
    class TargetOption(UVConfigBase):
        class TargetArmAds(UVConfigBase):

            misc_ads: UVArmAdsMisc
            compiler_ads: UVCads
            assembler_ads: UVAads
            linker_ads: UVLDads

            def __init__(self, elem: ET.Element | None = None) -> None:
                super().__init__(elem if elem is not None else "TargetArmAds")
                assert self.tag == "TargetArmAds"
                self.valid_keys = dict.fromkeys(("ArmAdsMisc", "Cads", "Aads", "LDads"))

                self.load()

                self.misc_ads = UVArmAdsMisc(self.find("./ArmAdsMisc"))
                self.compiler_ads = UVCads(self.find("./Cads"))
                self.assembler_ads = UVAads(self.find("./Aads"))
                self.linker_ads = UVLDads(self.find("./LDads"))

                self.subconfigs = [
                    self.misc_ads,
                    self.compiler_ads,
                    self.assembler_ads,
                    self.linker_ads,
                ]

        common_opt: UVTargetCommonOption
        common_prop: UVCommonProperty
        dll_opt: UVDllOption
        dbg_opt: UVDebugOption
        util: UVUtilities
        arm_ads: TargetArmAds

        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "TargetOption")
            assert self.tag == "TargetOption"

            self.valid_keys = dict.fromkeys(
                (
                    "TargetCommonOption",
                    "CommonProperty",
                    "DllOption",
                    "DebugOption",
                    "Utilities",
                    "TargetArmAds",
                )
            )

            self.load()

            self.common_opt = UVTargetCommonOption(self.find("./TargetCommonOption"))
            self.common_prop = UVCommonProperty(self.find("./CommonProperty"))
            self.dll_opt = UVDllOption(self.find("./DllOption"))
            self.dbg_opt = UVDebugOption(self.find("./DebugOption"))
            self.util = UVUtilities(self.find("./Utilities"))
            self.arm_ads = UVTarget.TargetOption.TargetArmAds(
                self.find("./TargetArmAds")
            )

            self.subconfigs = [
                self.common_opt,
                self.common_prop,
                self.dll_opt,
                self.dbg_opt,
                self.util,
                self.arm_ads,
            ]

    targ_opt: TargetOption

    class Groups(UVConfigBase):
        groups: list[UVGroup]
        _group_names: list[str]

        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "Groups")
            self.valid_keys = {"Group": None}

            self.load()

            self.groups = []
            for elem in self.iterfind("./Group"):
                self.groups.append(UVGroup(elem))

            self.subconfigs = [g for g in self.groups]

            self._group_names = [g.name for g in self.groups]

        @property
        def group_names(self):
            return tuple(self._group_names)

        def add_group(self, group: UVGroup):
            assert not group.name in self._group_names, f"{group.name} exists"
            self.groups.append(group)
            self.subconfigs.append(group)
            self._group_names.append(group.name)

    groups: Groups

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Target")
        assert self.tag == "Target", f"target xml tag {self.tag}"

        self.default_opts = {
            "ToolsetNumber": "0x4",
            "ToolsetName": "ARM_ADS",
            "pCCUsed": "6240000::V6.24::ARMCLANG",
            "uAC6": "1",
            "TargetName": "DefaultTargetName",
        }
        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys | {"TargetOption": None, "Groups": None}

        self.load()

        self.targ_opt = UVTarget.TargetOption(self.find("./TargetOption"))
        self.groups = UVTarget.Groups(self.find("./Groups"))

        self.subconfigs = [self.targ_opt, self.groups]

    @property
    def name(self) -> str:
        return self.options["TargetName"]

    @name.setter
    def name(self, val: str):
        assert (
            isinstance(val, str) and val.isidentifier()
        ), f"invalid target name: {val}"
        self.options["TargetName"] = val


class UVRTE(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "RTE")
        assert self.tag == "RTE", f"RTE xml tag {self.tag}"
        self.option_keys = self.valid_keys = dict.fromkeys(
            ("apis", "components", "files")
        )

        self.load()


class UVLayer(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Layer")
        assert self.tag == "Layer", f"layer xml tag {self.tag}"
        self.option_keys = self.valid_keys = {"LayName": None, "LayPrjMark": None}

        self.load()


class UVProject(UVConfigBase):
    class Targets(UVConfigBase):
        targets: list[UVTarget]
        _target_names: list[str]

        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "Targets")
            assert self.tag == "Targets"

            self.valid_keys = {"Target": None}

            self.load()

            self.targets = []
            for elem in self.iterfind("./Target"):
                self.targets.append(UVTarget(elem))
            if not self.targets:
                warn("no target found, adding a default target")
                self.targets.append(UVTarget(None))

            self.subconfigs = [t for t in self.targets]

            self._target_names = [targ.name for targ in self.targets]

        @property
        def target_names(self) -> list[str]:
            return self._target_names

        def add_target(self, targ: UVTarget):
            assert not targ.name in self._target_names, f"target {targ.name} exists"
            self.targets.append(targ)
            self.subconfigs.append(targ)
            self.target_names.append(targ.name)

    class Layers(UVConfigBase):
        layers: list[UVLayer]

        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "Layers")
            assert self.tag == "Layers"

            self.valid_keys = {"Layer": None}
            self.load()

            self.layers = []
            for elem in self.iterfind("./Layer"):
                self.layers.append(UVLayer(elem))
            self.subconfigs = [l for l in self.layers]

    class LayerInfo(UVConfigBase):
        # layers: 'Layers'
        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "LayerInfo")
            assert self.tag == "LayerInfo"
            self.valid_keys = {"Layers": None}

            self.load()

            self.layers = UVProject.Layers(self.find("./Layers"))
            self.subconfigs = [self.layers]

    targets: Targets
    rte_info: UVRTE
    layers: LayerInfo

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Project")
        assert self.tag == "Project", f"project xml tag {self.tag}"

        self.default_opts = {
            "SchemaVersion": "2.1",
            "Header": "### uVision Project, (C) Keil Software",
        }
        self.option_keys = dict.fromkeys(self.default_opts)
        self.valid_keys = self.option_keys | dict.fromkeys(
            ("Targets", "RTE", "LayerInfo")
        )

        self.load()

        # self.targets, self.layers = [], []

        self.targets = UVProject.Targets(self.find("./Targets"))
        self.rte_info = UVRTE(self.find("./RTE"))
        self.layers = UVProject.LayerInfo(self.find("./LayerInfo"))

        self.subconfigs = [self.targets, self.rte_info, self.layers]

        self.link()

    def write(self, fn: str):
        with open(fn, "w", encoding="utf8") as f:
            # f.write('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n')
            f.write(repr(self))

    def __repr__(self, *_) -> str:
        rep = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        rep += '<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        rep += 'xsi:noNamespaceSchemaLocation="project_projx.xsd">\n'
        rep += super().__repr__(0, False)
        rep += "</Project>\n"
        return rep


def test_config():
    cand = glob.glob("./*.uvprojx")[0]
    print(cand)
    tree = ET.parse("./tmp3.uvprojx")
    proj = UVProject(tree.getroot())
    # proj = UVPorject(None)

    proj.sync_options()

    print(
        proj.targets.targets[0].targ_opt.arm_ads.compiler_ads.various_controls.options
    )
    proj.write("out.uvprojx")

    print(proj.targets.targets[0].targ_opt.common_opt.options)


def test_config2():
    cand = glob.glob("./*.uvprojx")[0]
    print(cand)
    tree = ET.parse(cand)
    proj = UVProject(tree.getroot())
    print(proj)
    proj.sync_options()


if __name__ == "__main__":
    test_config()
