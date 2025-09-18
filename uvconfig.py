# from . import uvstrap

import xml.etree.ElementTree as ET
from typing import Self
import copy
from warnings import warn



class UVConfigBase(ET.Element):
    default_vals: dict[str, str]
    valid_keys: set[str]
    option_keys: set[str]
    options: dict[str, str | None]
    subconfigs: list

    def __init__(self, elem: ET.Element | str = "") -> None:
        if isinstance(elem, ET.Element):
            # copy
            super().__init__(elem.tag, elem.attrib)
            for sube in elem:
                self.append(sube)
        else:
            assert isinstance(elem, str)
            super().__init__(elem)
        self.default_vals = dict()
        self.valid_keys = set()
        self.option_keys = set()
        self.options = dict()
        self.subconfigs = []

    def load_default(self: Self):
        subs: set[str] = set()
        valid_keys: set[str] = self.valid_keys | set(self.default_vals)
        for elem in self:
            if not elem.tag in valid_keys:
                warn(f"{elem.tag} is not a valid tag in {self.tag}")
                self.remove(elem)
            else:
                subs.add(elem.tag)
        for tag in set(self.default_vals) - subs:
            sube = ET.Element(tag)
            sube.text = self.default_vals[tag]
            warn(
                f"adding default elem <{tag}>{self.default_vals[tag]}<{tag}/> in {self.tag}"
            )
            self.append(sube)

    def load_options(self: Self):
        for key in self.option_keys:
            assert key.isidentifier()
            elem: ET.Element | None = self.find(f"./{key}")
            if elem is None:
                warn(f"expected option <{key}>...<{key}/>")
                self.options[key] = (
                    self.default_vals[key] if key in self.default_vals else ""
                )
            else:
                self.options[key] = elem.text
    def sync_options(self: Self,recurse:bool=True):
        for key, val in self.options.items():
            assert key.isidentifier()
            elem: ET.Element | None = self.find(f"./{key}")
            if elem is None:
                elem = ET.Element(key)
                self.append(elem)
            elem.text = val
        if recurse:
            for sube in self.subconfigs:
                sube.sync_options(recurse)
    def link(self: Self,recurse:bool=True):
        # Remove existing children that match subconfig tags
        subconfig_tags = {sub.tag:i for i,sub in enumerate(self.subconfigs)}
        for i in range(len(self)):
            if self[i].tag in subconfig_tags:
                self[i]=self.subconfigs[subconfig_tags[self[i].tag]]
        if recurse:
            for sube in self.subconfigs:
                sube.link(recurse)


class UVTargetCommonOption(UVConfigBase):
    class TargetStatus(UVConfigBase):
        def __init__(self, elem: ET.Element | None) -> None:
            super().__init__(elem if elem is not None else "TargetStatus")
            assert self.tag == "TargetStatus", f"target status xml tag {self.tag}"

            self.default_vals = {
                "Error": "0",
                "ExitCodeStop": "0",
                "ButtonStop": "0",
                "NotGenerated": "0",
                "InvalidFlash": "1",
            }
            self.option_keys = set(self.default_vals.keys())
            self.valid_keys = self.option_keys

            self.load_default()
            self.load_options()
            self.subconfigs=[]#unused

    target_status: TargetStatus

    class CostumeCommands(UVConfigBase):
        def __init__(
            self, elem: ET.Element | None, id: str = "U", default_tag: str = ""
        ) -> None:
            super().__init__(elem if elem is not None else default_tag)
            assert self.tag == default_tag, f"costume command xml tag {self.tag}"

            self.default_vals = {
                "RunUserProg1": "0",
                "RunUserProg2": "0",
                "UserProg1Name": "",
                "UserProg2Name": "",
                "UserProg1Dos16Mode": "0",
                "UserProg2Dos16Mode": "0",
                f"nStop{id}1X": "0",
                f"nStop{id}2X": "0",
            }
            self.option_keys = set(self.default_vals.keys())
            self.valid_keys = self.option_keys

            self.load_default()
            self.load_options()
            self.subconfigs=[]#unused

    before_compile: CostumeCommands
    before_make: CostumeCommands
    after_make: CostumeCommands

    def __init__(self, elem: ET.Element | None) -> None:
        super().__init__(elem if elem is not None else "TargetCommonOption")
        assert self.tag == "TargetCommonOption", f"common option xml tag {self.tag}"

        self.default_vals = {
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
        self.option_keys = set(self.default_vals.keys()) | {"OutputName"}
        self.valid_keys = self.option_keys | {
            "TargetStatus",
            "BeforeCompile",
            "BeforeMake",
            "AfterMake",
        }

        self.load_default()
        self.load_options()

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
        self.subconfigs = [self.target_status, self.before_compile, self.before_make, self.after_make]


class UVCommonPorperty(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "TargetCommonProperty")
        assert self.tag == "CommonProperty", f"common property xml tag {self.tag}"

        self.default_vals = {
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
        self.option_keys = set(self.default_vals.keys())
        self.valid_keys = self.option_keys

        self.load_default()
        self.load_options()
        self.subconfigs=[]#unused


class UVArmAdsMisc(UVConfigBase):
    class OnChipMemories(UVConfigBase):
        class Memory(UVConfigBase):
            def __init__(self, elem: ET.Element | None = None, tag: str = ""):
                super().__init__(elem if elem is not None else tag)
                assert self.tag == tag, f"memory xml tag {self.tag}"

                self.default_vals = {
                    "Type": "0",
                    "StartAddress": "0x0",
                    "Size": "0x0",
                }
                self.option_keys = set(self.default_vals.keys())
                self.valid_keys = self.option_keys

                self.load_default()
                self.load_options()
                self.subconfigs=[]#unused   

        ocms: list[Memory]
        irams: list[Memory]
        iroms: list[Memory]
        ocr_rvct: list[Memory]  # represent vector

        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "OnChipMemories")
            assert self.tag == "OnChipMemories", f"on chip memories xml tag {self.tag}"

            self.ocms, self.irams, self.iroms, self.ocr_rvct = [], [], [], []
            for i in range(1, 7):
                self.ocms.append(
                    UVArmAdsMisc.OnChipMemories.Memory(
                        self.find(f"./Ocm{i}"), f"Ocm{i}"
                    )
                )
            for tag in ("I", "X"):
                self.irams.append(
                    UVArmAdsMisc.OnChipMemories.Memory(
                        self.find(f"./{tag}RAM"), f"{tag}RAM"
                    )
                )
                self.iroms.append(
                    UVArmAdsMisc.OnChipMemories.Memory(
                        self.find(f"./{tag}ROM"), f"{tag}ROM"
                    )
                )
            for i in range(1, 11):
                self.ocr_rvct.append(
                    UVArmAdsMisc.OnChipMemories.Memory(
                        self.find(f"./OCR_RVCT{i}"), f"OCR_RVCT{i}"
                    )
                )
            self.subconfigs = self.ocms + self.irams + self.iroms + self.ocr_rvct

    on_chip_memories: OnChipMemories

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "ArmAdsMisc")
        assert self.tag == "ArmAdsMisc", f"target arm ads xml tag {self.tag}"

        self.default_vals = {
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
        self.option_keys = set(self.default_vals.keys())
        self.valid_keys = self.option_keys | {"OnChipMemories"}

        self.load_default()
        self.load_options()

        self.on_chip_memories = UVArmAdsMisc.OnChipMemories(
            self.find("./OnChipMemories")
        )
        self.subconfigs = [self.on_chip_memories]


class UVVariousControls(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "VariousControls")
        assert self.tag == "VariousControls", f"various controls xml tag {self.tag}"

        self.default_vals = {
            "MiscControls": "",
            "Define": "",
            "Undefine": "",
            "IncludePath": "",
        }
        self.option_keys = set(self.default_vals.keys())
        self.valid_keys = self.option_keys

        self.load_default()
        self.load_options()
        self.subconfigs=[]#unused


class UVCads(UVConfigBase):  # compiler arm developer suite
    various_controls: UVVariousControls

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Cads")
        assert self.tag == "Cads", f"cads xml tag {self.tag}"

        self.default_vals = {
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

        self.option_keys = set(self.default_vals.keys())
        self.valid_keys = self.option_keys | {"VariousControls"}

        self.load_default()
        self.load_options()

        self.various_controls = UVVariousControls(self.find("./VariousControls"))
        self.subconfigs = [self.various_controls]


class UVAads(UVConfigBase):  # assembler arm developer suite
    various_controls: UVVariousControls

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Aads")
        assert self.tag == "Aads", f"aads xml tag {self.tag}"

        self.default_vals = {
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

        self.option_keys = set(self.default_vals.keys())
        self.valid_keys = self.option_keys | {"VariousControls"}

        self.load_default()
        self.load_options()

        self.various_controls = UVVariousControls(self.find("./VariousControls"))
        self.subconfigs = [self.various_controls]


class UVLDads(UVConfigBase):  # linker arm developer suite
    various_controls: UVVariousControls

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "LDads")
        assert self.tag == "LDads", f"lads xml tag {self.tag}"

        self.default_vals = {
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

        self.option_keys = set(self.default_vals.keys())
        self.valid_keys = self.option_keys

        self.load_default()
        self.load_options()
        self.subconfigs=[]#unused

class UVGroup(UVConfigBase):
    class File(UVConfigBase):
        def __init__(self, elem: ET.Element | None = None) -> None:
            super().__init__(elem if elem is not None else "File")
            assert self.tag == "File", f"file xml tag {self.tag}"

            self.option_keys = {'FileName', 'FileType', 'FilePath'}
            self.valid_keys = self.option_keys

            self.load_default()
            self.load_options()
            self.subconfigs=[]#unused
    files: list[File]
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Group")
        assert self.tag == "Group", f"group xml tag {self.tag}"

        self.option_keys = {'GroupName'}
        self.valid_keys = self.option_keys | {"Files"}

        self.load_default()
        self.load_options()

        self.files = []
        for elem in self.iterfind("./Files/File"):
            self.files.append(UVGroup.File(elem))
        self.subconfigs = self.files

class UVTarget(UVConfigBase):
    common_opt: UVTargetCommonOption
    common_prop: UVCommonPorperty
    misc_ads: UVArmAdsMisc
    compiler_ads: UVCads
    assembler_ads: UVAads
    linker_ads: UVLDads

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Target")
        assert self.tag == "Target", f"target xml tag {self.tag}"

        self.default_vals = {
            "ToolsetNumber": "0x4",
            "ToolsetName": "ARM_ADS",
            "pCCUsed": "6240000::V6.24::ARMCLANG",
            "uAC6": "1",
        }
        self.option_keys = set(self.default_vals.keys()) | {"TargetName"}
        self.valid_keys = self.option_keys | {"TargetOption", "Groups"}

        self.load_default()
        self.load_options()

        self.common_opt = UVTargetCommonOption(
            self.find("./TargetOption/TargetCommonOption")
        )
        self.common_prop = UVCommonPorperty(self.find("./TargetOption/CommonProperty"))
        # (debug) dlloptions
        # debug options
        # utilities (flash menu command)
        self.misc_ads = UVArmAdsMisc(
            self.find("./TargetOption/TargetArmAds/ArmAdsMisc")
        )
        self.compiler_ads = UVCads(self.find("./TargetOption/TargetArmAds/Cads"))
        self.assembler_ads = UVAads(self.find("./TargetOption/TargetArmAds/Aads"))
        self.linker_ads = UVLDads(self.find("./TargetOption/TargetArmAds/LDads"))
        self.subconfigs = [self.common_opt, self.common_prop, self.misc_ads, self.compiler_ads, self.assembler_ads, self.linker_ads]


class UVRTE(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "RTE")
        assert self.tag == "RTE", f"RTE xml tag {self.tag}"
        self.option_keys = self.valid_keys = {"apis", "components", "files"}
        self.load_default()
        self.load_options()
        self.subconfigs=[]#unused


class UVLayer(UVConfigBase):
    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Layer")
        assert self.tag == "Layer", f"layer xml tag {self.tag}"
        self.option_keys = self.valid_keys = {"LayName", "LayPrjMark"}
        self.load_default()
        self.load_options()
        self.subconfigs=[]#unused


class UVPorject(UVConfigBase):
    targets: list[UVConfigBase]
    layers: list[UVConfigBase]
    rte_info: UVConfigBase

    def __init__(self, elem: ET.Element | None = None) -> None:
        super().__init__(elem if elem is not None else "Project")
        assert self.tag == "Project", f"project xml tag {self.tag}"

        self.default_vals = {
            "SchemaVersion": "2.1",
            "Header": "### uVision Project, (C) Keil Software",
        }
        self.option_keys = set(self.default_vals.keys())
        self.valid_keys = self.option_keys| {"Targets", "RTE", "LayerInfo"}
        self.load_default()

        self.targets, self.layers = [], []

        for t_elem in self.iterfind("./Targets/Target"):
            self.targets.append(UVTarget(t_elem))
        for t_elem in self.iterfind("./LayerInfo/Layers/Layer"):
            self.layers.append(UVLayer(t_elem))
        self.rte_info = UVRTE(self.find("./RTE"))
        self.subconfigs = self.targets + self.layers + [self.rte_info]

        self.link()


def test_config():
    tree = ET.parse("./tmp2.uvprojx")
    proj = UVPorject(tree.getroot())
    print(proj)
    proj.sync_options()
    ET.ElementTree(proj).write("out.uvprojx", encoding="utf-8", xml_declaration=True,short_empty_elements=False)


if __name__ == "__main__":
    test_config()
