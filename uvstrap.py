import os
import argparse
import sys
import glob
import subprocess
from warnings import warn
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

from . import default_dat

# proj layout:
#
# Startup:
#  contains startup_stm32f10x_hd.s: high density device table
#  from {}/Libraries/CMSIS/CM3/DeviceSupport/ST/STM32F10x/startup/arm
# Lib:
#  SPL: standard peripheral lib, microcontroller specific
#   contains misc.c and stm32f10x_xxx.c from {}/Libraries/xxx_Driver/src
#  CMSIS: cortex microcontroller system interface standard,
#         as well as device family pack (xxx_DFP/<version> and CMSIS/<version>/CMSIS)
#         see https://arm-software.github.io/CMSIS_6/v6.0.0/Core/cmsis_core_files.html
#   <device>.h defines peripheral access. in {}/Device/Include
#   system_<device>.h defines system initor. in {}/Device/Include
#   startup_<device>_(cl|hd).s defines INT startup. in {}/Device/Source/ARM
#   system_<Device>.c implements system initor. in {}/Device/Source
#   core_<cpu>.h cpu and core access to cover vender specific funcionalities
#
#
#
#   D:\program2\ARMKeil_v5_packs\ARM\CMSIS\6.2.0\CMSIS\Core\Include\core_cm3.h
#   D:\program2\ARMKeil_v5_packs\Keil\STM32F1xx_DFP\2.4.1\Device\Source\system_stm32f10x.c

print_lock = threading.Lock()


def run_command(cmd: list[str]):
    proc = subprocess.run(cmd, capture_output=True)
    with print_lock:
        print(
            f'\033[38;5;10m>> {" ".join(cmd)}: {proc.returncode}'
            f"(\033[38;5;9m{proc.stderr.decode()}\033[38;5;10m)\033[0m",
            flush=True,
        )


def copy_file(src: str, dst: str):
    CHUNK_SIZE = 4096
    if not os.path.isfile(src):
        with print_lock:
            print(
                f"\033[38;5;9m>>Copy-File {src} to {dst}: (src not exist)\033[0m",
                flush=True,
            )
        return
    if not (os.path.isfile(dst) or os.path.isdir(dst)):
        with print_lock:
            print(
                f"\033[38;5;9m>>Copy-File {src} to {dst}: (dst not exist)\033[0m",
                flush=True,
            )
        return
    if os.path.isdir(dst):
        dst = os.path.normpath(dst + "/" + os.path.basename(src))

    # compare file content
    needs_copy = True
    if os.path.isfile(dst) and os.path.getsize(src) == os.path.getsize(dst):
        needs_copy = False
        with open(src, "rb") as fsrc, open(dst, "rb") as fdst:
            while not fsrc.peek() != b"" and fdst.peek() != b"":
                hash_src, hash_dst = hash(fsrc.read(CHUNK_SIZE)), hash(
                    fdst.read(CHUNK_SIZE)
                )
                if hash_src != hash_dst:
                    needs_copy = True
                    break
    if not needs_copy:
        with print_lock:
            print(f"\033[38;5;10m>>Copy-File: up-to-date: {dst}\033[0m", flush=True)
    else:
        run_command(["cp", os.path.normpath(src), os.path.normpath(dst)])


def content_replace(fn: str, matching: re.Pattern | str, replacement: str):
    err_msg: str = ""
    fn = os.path.normpath(fn)
    try:
        with open(fn, "r", encoding="utf-8") as f:
            data = f.read()
        data = re.sub(matching, replacement, data, flags=re.MULTILINE | re.ASCII)
        with open(fn, "w", encoding="utf-8") as f:
            f.write(data)
    except Exception as e:
        err_msg = f"{type(e),str(e)}"
    print(
        f"\033[38;5;10m>>Replace-Content {fn} from {matching} to {replacement}: "
        f"(\033[38;5;9m{err_msg}\033[38;5;10m)\033[0m",
        flush=True,
    )


def parse_args(args: list[str]) -> dict:
    default_stsd = (
        os.environ["ARG_STSOFTWARE"] if "ARG_STSOFTWARE" in os.environ else ""
    )
    default_kpd = os.environ["ARG_KEILPACK"] if "ARG_KEILPACK" in os.environ else ""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--st_software_dir",
        type=str,
        default=default_stsd,
        help="board specific sources, mainly \033[38;5;9mstandard peripheral lib\033[0m. installed from "
        "https://www.st.com/en/embedded-software/stm32-standard-peripheral-libraries.html. "
        f"default \033[38;5;10m$env:ARG_STSOFTWARE = {default_stsd}\033[0m",
    )
    parser.add_argument(
        "--keil_pack_dir",
        type=str,
        default=default_kpd,
        help="package dir specified at installing \033[38;5;9mmdk\033[0m. "
        "see https://arm-software.github.io/CMSIS_6/v6.0.0/Core/cmsis_core_files.html. "
        f"default \033[38;5;10m$env:ARG_KEILPACK = {default_kpd}\033[0m",
    )
    parser.add_argument(
        "--project_dir",
        type=str,
        default=os.path.normpath("."),
        help="project dir to be bootstrapped to. "
        f"default \033[38;5;10m. (aka {os.path.abspath('.')})\033[0m",
    )
    parser.add_argument(
        "--dfp_name",
        type=str,
        default="STM32F1xx_DFP",
        help="CMSIS device family pack name. default \033[38;5;10mSTM32F1xx_DFP\033[0m",
    )
    parser.add_argument(
        "--spl_name",
        type=str,
        default="STM32F10x_StdPeriph_Driver",
        help="Standard Peripheral Lib. default \033[38;5;10mSTM32F10x_StdPeriph_Driver\033[0m",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="cleanup bootstrapped files. default \033[38;5;10mFalse\033[0m",
    )
    parser.add_argument(
        "--amend_spl",
        type=bool,
        default=True,
        help="fix out-of-date SPL "
        "conflicting arm compiler v6's naming convention change "
        "(NVIC_Type.IP renamed to NVIC_Type.IPR). "
        "default \033[38;5;10mTrue\033[0m",
    )
    res = parser.parse_args(args)

    st_software_dir = os.path.normpath(os.path.abspath(res.st_software_dir))
    project_dir = os.path.normpath(os.path.abspath(res.project_dir))
    keil_pack_dir = os.path.normpath(os.path.abspath(res.keil_pack_dir))
    print(
        f"st_software_dir: {st_software_dir}\nproject_dir: {project_dir}\npackage dir: {keil_pack_dir}"
    )

    if not os.path.isdir(st_software_dir):
        warn(f"cant access st_software_dir: {st_software_dir}")
    if not os.path.isdir(project_dir):
        warn(f"cant access project dir: {project_dir}")

    return {
        "st_software_dir": st_software_dir,
        "project_dir": project_dir,
        "keil_pack_dir": keil_pack_dir,
        "dfp_name": res.dfp_name,
        "spl_name": res.spl_name,
        "clean": res.clean,
        "amend_spl": res.amend_spl,
    }


def bootstrap(args: dict):
    EXEC_MAX_WORKERS = 8
    st_software_dir = args["st_software_dir"]
    project_dir = args["project_dir"]
    keil_pack_dir = args["keil_pack_dir"]
    dfp_name = args["dfp_name"]
    spl_name = args["spl_name"]
    spl_targ_device = spl_name.partition("_")[0].lower()
    amend_spl = args["amend_spl"]

    assert (
        len(glob.glob(project_dir + "/*.uvprojx")) > 0
    ), f"{project_dir} is not a keil project dir"

    print("finding spl")
    spl_base = os.path.normpath(st_software_dir + "/Libraries/" + spl_name)
    print(f"spl dir: {spl_base}")
    assert os.path.isdir(spl_base), "no spl found"
    spl_src = glob.glob(spl_base + "/src/*.c")
    spl_inc = glob.glob(spl_base + "/inc/*.h")

    print("finding cmsis - device family pack")
    dfp_cands = glob.glob(keil_pack_dir + "/Keil/" + dfp_name + "/*/Device")
    print(f"CMSIS-device family pack candidates: {dfp_cands}")
    assert len(dfp_cands) > 0, "no cmsis-dfp found"
    dfp_base = dfp_cands[0]
    dfp_inc = glob.glob(dfp_base + "/Include/*.h")
    dfp_sysinit = os.path.normpath(dfp_base + "/Source/system_stm32f10x.c")
    assert os.path.isfile(dfp_sysinit), f"cant find {dfp_sysinit}"
    dfp_startup = os.path.normpath(dfp_base + "/Source/ARM/startup_stm32f10x_hd.s")
    assert os.path.isfile(dfp_startup), f"cant find {dfp_startup}"

    print("finding cmsis - core (vende specific)")
    cmsis_cands = glob.glob(keil_pack_dir + "/ARM/CMSIS/*/CMSIS")
    print(f"CMSIS core candidates: {cmsis_cands}")
    assert len(cmsis_cands) > 0, "no cmsis-core found"
    cmsis_base = cmsis_cands[0]
    cmsis_core_h = glob.glob(cmsis_base + "/Core/Include/*.h")
    cmsis_core_h_ex = glob.glob(cmsis_base + "/Core/Include/m-profile/*.h")
    cmsis_core_h += glob.glob(cmsis_base + "/Core/Include/a-profile/*.h")
    # cmsis_core_h_ex += glob.glob(cmsis_base + "/Core/Include/r-profile/*.h")
    cmsis_core_src = glob.glob(cmsis_base + "/Core/Source/*.c")

    print("bootstrapping")
    lib_dest = os.path.normpath(project_dir + "/Lib/")
    spl_dest = os.path.normpath(lib_dest + "/SPL/")
    cmsis_dest = os.path.normpath(lib_dest + "/CMSIS/")
    cmsis_core_dest = os.path.normpath(lib_dest + "/CMSIS/Core/")
    cmsis_core_ex_dest = os.path.normpath(lib_dest + "/CMSIS/Core/m-profile/")
    dfp_dest = os.path.normpath(lib_dest + "/CMSIS/DFP/")

    with ThreadPoolExecutor(max_workers=EXEC_MAX_WORKERS) as e:
        e.submit(run_command, ["mkdir", lib_dest])
    with ThreadPoolExecutor(max_workers=EXEC_MAX_WORKERS) as e:
        e.submit(run_command, ["mkdir", spl_dest])
        e.submit(run_command, ["mkdir", cmsis_dest])
    with ThreadPoolExecutor(max_workers=EXEC_MAX_WORKERS) as e:
        e.submit(run_command, ["mkdir", cmsis_core_dest])
        e.submit(run_command, ["mkdir", dfp_dest])
    with ThreadPoolExecutor(max_workers=EXEC_MAX_WORKERS) as e:
        e.submit(run_command, ["mkdir", cmsis_core_ex_dest])

    with ThreadPoolExecutor(max_workers=EXEC_MAX_WORKERS) as e:
        for spl in spl_src + spl_inc:
            e.submit(copy_file, os.path.normpath(spl), spl_dest)
        for inc in dfp_inc:
            e.submit(copy_file, os.path.normpath(inc), dfp_dest)
        for inc in cmsis_core_h:
            e.submit(copy_file, os.path.normpath(inc), cmsis_core_dest)
        for inc in cmsis_core_h_ex:
            e.submit(copy_file, os.path.normpath(inc), cmsis_core_ex_dest)
        for src in cmsis_core_src:
            e.submit(copy_file, os.path.normpath(src), cmsis_core_dest)

        e.submit(copy_file, dfp_sysinit, dfp_dest)
        e.submit(copy_file, dfp_startup, dfp_dest)

    if amend_spl:
        print("amending with SPL (NVIC->IP to NVIC->IPR)")
        content_replace(spl_dest + "/misc.c", "NVIC\\s*->IP\\s*", "NVIC->IPR")

    #
    # autoconfig

    stmx_conf_h = f"./src/{spl_targ_device}_conf.h"
    if not os.path.isfile(stmx_conf_h):
        warn(f"\033[38;5;9mcant find {stmx_conf_h}, starting autoconfig\033[0m")
        assert (
            spl_targ_device in default_dat.stmx_conf_h_defaults
        ), f"no default ..._conf.h for {spl_targ_device}"

        with open(stmx_conf_h, "wb") as f:
            f.write(
                default_dat.decompress(
                    default_dat.stmx_conf_h_defaults[spl_targ_device]
                )
            )

    rte_comp_h = "./src/RTE_Components.h"
    if not os.path.isfile(rte_comp_h):
        warn(f"\033[38;5;9mcant find {rte_comp_h}, creating one\033[0m")
        with open(rte_comp_h, "w", encoding="utf-8") as f:
            f.write(default_dat.rte_conf_h_defaults.format(spl_targ_device))


def cleanup(args: dict):
    run_command(["rm", "-rf", os.path.normpath(args["project_dir"] + "/Lib")])


def strap():
    args = parse_args(sys.argv[1:])
    if args["clean"]:
        cleanup(args)
        del args["clean"]
    bootstrap(args)


if __name__ == "__main__":
    strap()
