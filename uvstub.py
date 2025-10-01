import argparse
from typing import Literal, TypedDict
import os
import glob
from collections import defaultdict
import xml.etree.ElementTree as ET
from warnings import warn
from concurrent.futures import ThreadPoolExecutor
import json
import time

from .uvconfig import UVProject, UVTarget, UVGroup
from .uvstrap import copy_file, copy_file_to_stub, copy_file_from_stub, run_command

# type args_t = dict[Literal["option", "project_dir", "stub_dir", "keil_dir"], str]


class args_t(TypedDict):
    option: str
    project_dir: str
    stub_dir: str
    keil_dir: str
    inplace: bool
    local_std: bool
    files: str
    group: str
    par: bool


def parse_args() -> args_t:

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "option",
        choices=[
            "gen_stub",
            "sync_stub",
            "status",
            "nop",
            "add_group",
            "add_target",
            "add_src",
            "add_inc",
        ],
        help="operation to perform with stub",
    )
    parser.add_argument(
        "--project_dir",'--project-dir',
        type=str,
        default=".",
        help="directory of the project. "
        f"default . = \033[38;5;10m{os.path.abspath(os.curdir)}\033[0m",
    )
    parser.add_argument(
        "--stub_dir",'--stub-dir',
        type=str,
        default="./stub",
        help="directory of the stub files. "
        f'default ./stub = \033[38;5;10m{os.path.abspath(os.curdir+"/stub")}\033[0m',
    )
    default_keil_dir: str = os.environ["ARG_KEIL"] if "ARG_KEIL" in os.environ else ""
    parser.add_argument(
        "--keil_dir",'--keil-dir',
        type=str,
        default=default_keil_dir,
        help="directory of keil MDK "
        "installation dir to find armclang includes, default $env:ARG_KEIL = "
        f"\033[38;5;10m{default_keil_dir}\033[0m",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="generate compile_commands.json at project_dir " "rather than stub.",
    )
    parser.add_argument(
        "--local_std",'--local-std',
        action="store_true",
        help="copy std includes to ./stub/stdstub (or ./stdstub with inplace)"
        "so as to fix incompatibilities in std includes",
    )
    parser.add_argument('--no_local_std','--no-local-std',action='store_true',help='disable local_std option'
                        'if both are not specified, local_std is used')
    parser.add_argument(
        "--files",
        type=str,
        default="",
        help="file or dir pattern recognized by glob.glob()",
    )
    parser.add_argument(
        "group", nargs="?", default="", help="specify a name for target, group, etc"
    )
    parser.add_argument(
        "--no_par","--no-par", action="store_true", help="disable parallel copying"
    )

    res = parser.parse_args()
    # canonicalize paths
    project_dir = os.path.normpath(os.path.abspath(res.project_dir))
    assert os.path.isdir(project_dir), f"project_dir {project_dir} is not a directory"
    stub_dir = os.path.normpath(os.path.abspath(res.stub_dir))
    run_command(["mkdir", stub_dir])
    assert os.path.isdir(stub_dir), f"stub_dir {stub_dir} is not a directory"
    assert (
        os.path.commonpath([project_dir, stub_dir]) != stub_dir
    ), f"stub_dir {stub_dir} corrupts with project_dir {project_dir}"

    # assert not (res.local_std and res.inplace), "invalid option combination (currently)"
    assert not(res.local_std and res.no_local_std),'invalid option combination'

    return {
        "option": res.option,
        "project_dir": os.path.normpath(os.path.abspath(res.project_dir)),
        "stub_dir": os.path.normpath(os.path.abspath(res.stub_dir)),
        "keil_dir": os.path.normpath(os.path.abspath(res.keil_dir)),
        "inplace": res.inplace,
        "local_std": res.local_std or not res.no_local_std,
        "files": os.path.normpath(res.files),
        "group": res.group,
        "par": not res.no_par,
    }


class Manipulator:
    proj: UVProject
    args: args_t
    links: list[tuple[str, str]]
    proj_file: str

    def __init__(self, args: args_t) -> None:
        project_dir = args["project_dir"].rstrip("/\\")
        proj_name = os.path.basename(project_dir)
        if os.path.isfile(project_dir + f"/{proj_name}.uvprojx"):
            proj_file = project_dir + f"/{proj_name}.uvprojx"
        else:
            cands = glob.glob(project_dir + "/*.uvprojx")
            assert len(cands) > 0, f"no .uvprojx file found in {project_dir}"
            proj_file = cands[0]
        print(f"found project file {proj_file}")
        tree = ET.parse(proj_file)
        self.proj_file = proj_file
        self.proj = UVProject(tree.getroot())
        self.args = args
        self.links = []
        self.collect_links()

    @staticmethod
    def fn2stub(args: args_t, fn: str) -> str:
        rel_path = os.path.relpath(fn, args["project_dir"])
        stub_path = os.path.join(args["stub_dir"], rel_path)
        stub_path = os.path.normpath(os.path.abspath(stub_path))
        return stub_path

    @staticmethod
    def fn2proj(args: args_t, fn: str) -> str:
        rel_path = os.path.relpath(fn, args["stub_dir"])
        proj_path = os.path.join(args["project_dir"], rel_path)
        proj_path = os.path.normpath(proj_path)
        return proj_path

    @staticmethod
    def std2stub(args: args_t, fn: str) -> str:
        rel_path = os.path.relpath(fn, args["keil_dir"] + "/ARM/ARMCLANG/include")
        stub_path = os.path.normpath(
            (args["stub_dir"] if not args["inplace"] else args["project_dir"])
            + "/stdstub/"
            + rel_path
        )
        return stub_path

    @staticmethod
    def unwind_paths(paths: str) -> list[str]:
        return paths.replace(",", ";").split(";")

    def collect_files(self) -> defaultdict[str, dict[str, list[str]]]:
        ret = defaultdict(dict)
        for targ in self.proj.targets.targets:
            for group in targ.groups.groups:
                files = [file.path for file in group.files.files]
                for i in reversed(range(len(files))):
                    files[i] = os.path.normpath(os.path.abspath(files[i]))
                    if not os.path.isfile(files[i]):
                        warn(f"file {files[i]} not found, removed from list")
                        files.pop(i)
                    if "stub" in files[i]:
                        warn(f'skip {files[i]} for token "stub" in{files[i]}')
                        files.pop(i)
                ret[targ.name][group.name] = files
        return ret

    def collect_includes(
        self,
    ) -> defaultdict[str, dict[Literal["common", "ass_inc", "cmp_inc"], list[str]]]:
        ret = defaultdict(dict)
        for targ in self.proj.targets.targets:
            ret[targ] = {
                "common": self.unwind_paths(
                    targ.targ_opt.common_opt.options["IncludePath"]
                ),
                "ass_inc": self.unwind_paths(
                    targ.targ_opt.arm_ads.assembler_ads.various_controls.options[
                        "IncludePath"
                    ]
                ),
                "cmp_inc": self.unwind_paths(
                    targ.targ_opt.arm_ads.compiler_ads.various_controls.options[
                        "IncludePath"
                    ]
                ),
            }

        return ret

    def collect_links(self):
        self.links.clear()

        #
        # collect src files
        files: set[str] = set()
        for groups in self.collect_files().values():
            for fns in groups.values():
                files.update(fns)
        #        
        # collect headers
        for inc in self.collect_includes().values():
            for paths in inc.values():
                for p in paths:
                    # p is dir
                    if os.path.isdir(p):
                        for fn in glob.glob(os.path.join(p, "**", "*"), recursive=True):
                            if os.path.isfile(fn) and not "stub" in fn:
                                files.add(os.path.normpath(os.path.abspath(fn)))
                    # p is file
                    elif os.path.isfile(p) and not "stub" in p:
                        fn=p
                        files.add(os.path.normpath(os.path.abspath(fn)))

#
        # collect markdowns
        mds = glob.glob(self.args["project_dir"] + "/*.md") + glob.glob(
            self.args["project_dir"] + "/**/*.md"
        )
        mds = [f for f in mds if not "uvhelper" in f and not "stub" in f]
        if len(mds) < 10:
            print(f"\033[38;5;6mmarkdowns: {mds}\033[0m")
        else:
            print(f"\033[38;5;6mmarkdowns: {mds[:8]}...({len(mds)} in total)\033[0m")

        for md in mds:
            self.links.append((md, self.fn2stub(self.args, md)))

#
        # get links
        print(f"collected files: {len(files)}; markdowns: {len(self.links)}")
        for fn in files:
            fn = os.path.normpath(os.path.abspath(fn))
            if (
                os.path.commonpath([self.args["project_dir"], fn])
                != self.args["project_dir"]
            ):
                print(f"\033[38;5;9mcollect links: skip {fn}\033[0m")
                continue
            stub_fn = self.fn2stub(self.args, fn)
            self.links.append((fn, stub_fn))
        # print(self.links)
        # input()

    def collect_stdinc(self) -> list[tuple[str, str]]:
        incs = []
        if os.path.isdir(self.args["keil_dir"] + "/ARM/ARMCLANG/include"):
            for fn in glob.glob(self.args["keil_dir"] + "/ARM/ARMCLANG/include/*.h"):
                if os.path.isfile(fn):
                    incs.append((fn, self.std2stub(self.args, fn)))
        else:
            warn(
                f"\033[38;5;9mgen_stub: keil_dir {self.args['keil_dir']} is not valid, "
                "skip system includes\033[0m"
            )
        return incs

    def gen_stub(self) -> None:
        if not self.args["inplace"]:
            # if not inplace, copy and fix all source and header files
            # ask if stub exists
            items_in_stub = glob.glob(self.args["stub_dir"] + "/**/*", recursive=True)

            if len(items_in_stub) > 0:
                print(
                    f"\033[38;5;9mgen_stub: {len(items_in_stub)} items exists in stub: "
                    f"{items_in_stub if len(items_in_stub)<10 else '[...]'}\n"
                    "sure to gen stub?([n]/y)\033[0m"
                )
                if input().lower() != "y":
                    print("gen_stub: stopped early")
                    return

            # >if not self.args["inplace"]<

            #
            # update links
            self.collect_links()

            # copy files
            with ThreadPoolExecutor() as e:
                for fn, stub_fn in self.links:
                    if self.args["par"]:
                        e.submit(copy_file_to_stub, fn, stub_fn)
                    else:
                        copy_file_to_stub(fn, stub_fn)

                # # copy arm standard includes to ./stub/stub
                #
                # if os.path.isdir(self.args["keil_dir"] + "/ARM/ARMCLANG/include"):
                #     for fn in glob.glob(
                #         self.args["keil_dir"] + "/ARM/ARMCLANG/include/*.h"
                #     ):
                #         if os.path.isfile(fn):
                #             e.submit(copy_file, fn, self.sys2stub(self.args, fn))
                # else:
                #     warn(
                #         f"gen_stub: keil_dir {self.args['keil_dir']} is not valid, skip system includes"
                #     )

            # update local timestamp
            for fn, stub_fn in self.links:
                os.utime(fn)
        # if not self.args["inplace"]/>

        #
        #
        # if local_std, copy and fix stds.
        if self.args["local_std"]:
            stdinc_links = self.collect_stdinc()
            print(
                f"gen_stub: collected {len(stdinc_links)} std includes: {[os.path.basename(i[0]) for i in stdinc_links]}"
            )
            input()
            with ThreadPoolExecutor() as e:
                for fn, stub_fn in stdinc_links:
                    if self.args["par"]:
                        e.submit(copy_file_to_stub, fn, stub_fn)
                    else:
                        copy_file_to_stub(fn, stub_fn)

        #
        #
        # create compile_commands.json
        # for each file->.obj
        cmds: list[dict[Literal["directory", "command", "file", "output"], str]] = []
        for targ in self.proj.targets.targets:
            c_inc = (
                targ.targ_opt.arm_ads.compiler_ads.various_controls.options[
                    "IncludePath"
                ]
                .replace(",", ";")
                .split(";")
            )
            a_inc = (
                targ.targ_opt.arm_ads.assembler_ads.various_controls.options[
                    "IncludePath"
                ]
                .replace(",", ";")
                .split(";")
            )
            c_defines = (
                targ.targ_opt.arm_ads.compiler_ads.various_controls.options["Define"]
                .replace(",", ";")
                .split(";")
            )
            a_defines = (
                targ.targ_opt.arm_ads.assembler_ads.various_controls.options["Define"]
                .replace(",", ";")
                .split(";")
            )

            # std includes
            if self.args["local_std"]:
                c_inc.append(
                    os.path.normpath(
                        (
                            self.args["stub_dir"]
                            if not self.args["inplace"]
                            else self.args["project_dir"]
                        )
                        + "/stdstub"
                    )
                )
            elif os.path.isdir(self.args["keil_dir"] + "/ARM/ARMCLANG/include"):
                c_inc.append(
                    os.path.normpath(self.args["keil_dir"] + "/ARM/ARMCLANG/include")
                )
            else:
                warn("\033[38;5;9mskip standard headers include\033[0m")

            # commandline amendments
            # use armclang
            # armclang macros
            c_defines += ["__ARMCC_VERSION=6230050", "__ARM_ACLE"]  # "__ARM_COMPAT_H"]
            a_defines += ["__ARMCC_VERSION=6230050", "__ARM_ACLE"]  # "__ARM_COMPAT_H"]
            # built-in functions, see https://developer.arm.com/documentation/101754/0622/armclang-Reference/Compiler-specific-Intrinsics
            # void __breakpoint(int);
            c_defines += [f""]

            for group in targ.groups.groups:
                for file in group.files.files:
                    output = os.path.splitext(file.path)[0] + ".obj"
                    cmds.append(
                        {
                            "directory": self.args["stub_dir"],
                            "command": f"clang "
                            "-nostdinc -nostdinc++ -nostdlib -nostdlib++ "  # redirect std includes
                            "-ffreestanding -Dsize_t=unsigned "  # size_t problem and __asm__ error register
                            f'{" ".join(["-I"+inc for inc in (a_inc if file.path.endswith(".s")else c_inc)])} '
                            f'{" ".join(["-D"+defs for defs in (a_defines if file.path.endswith(".s")else c_defines)])}'
                            f"-o {output} -c {file.path}",
                            "file": file.path,
                            "output": output,
                        }
                    )
        print("generating compile_commands.json: ", end="")
        with open(
            (
                self.args["stub_dir"]
                if not self.args["inplace"]
                else self.args["project_dir"]
            )
            + "/compile_commands.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(cmds, f, indent=4)
        print("done")

    def collect_status(self) -> list[tuple[str, str]]:
        self.collect_links()
        ret: list[tuple[str, str]] = []
        assert len(set([l[0] for l in self.links]))==len(self.links),'multi key'
        for fn, stub_fn in self.links:
            if os.path.isfile(stub_fn) and os.path.getmtime(fn) < os.path.getmtime(
                stub_fn
            ):
                ret.append((fn, stub_fn))
        return ret

    def status(self):
        stat = self.collect_status()
        print(
            f"\033[38;5;6mstatus: {len(stat)} files change in stub{':' if len(stat)>0 else '.'}\033[0m"
        )
        for fn, stub_fn in stat:
            print(f"\033[38;5;10m{fn}  <-  {stub_fn}\033[0m")

    # sync from stub to project
    def sync_stub(self):
        status = self.collect_status()
        if len(status) == 0:
            print("\033[38;5;9msync_stub: not work to do\033[0m")
            return
        with ThreadPoolExecutor() as e:
            for fn, stub_fn in status:
                if self.args["par"]:
                    e.submit(copy_file_from_stub, stub_fn, fn)
                else:
                    copy_file_from_stub(stub_fn, fn)
                os.utime(fn)

    def write_proj(self, test=True):
        self.proj.write(self.proj_file + (".xml" if test else ""))

    def parse_targ_group(self) -> tuple[str, str]:
        target, _, group = self.args["group"].partition("/")
        if target.isdigit():
            target = self.proj.targets.target_names[int(target)]
        if group.isdigit() and target in self.proj.targets.target_names:
            idx = self.proj.targets.target_names.index(target)
            group = self.proj.targets.targets[idx].groups.group_names[int(group)]
        return target, group

    def add_target(self):
        targ_nm, _ = self.parse_targ_group()
        if targ_nm in self.proj.targets.target_names:
            warn(f"target {targ_nm} already exists")
            return
        targ = UVTarget()
        targ.name = targ_nm
        self.proj.targets.add_target(targ)
        self.write_proj(False)
        return targ

    def add_group(self):
        target, group = self.parse_targ_group()
        print(f"\033[38;5;10mtarget: {target}, group: {group}\033[0m")
        if not target in self.proj.targets.target_names:
            self.add_target()
        idx = self.proj.targets.target_names.index(target)
        targ = self.proj.targets.targets[idx]
        if group in targ.groups.group_names:
            warn(f"group \033[38;5;10m[{group}]\033[0m already exists")
            return
        g = UVGroup()
        g.name = group
        targ.groups.add_group(g)
        self.write_proj(False)

    def add_src(self):
        proj, stub, ptrn = (
            self.args["project_dir"],
            self.args["stub_dir"],
            self.args["files"],
        )
        assert not os.path.isabs(ptrn), "source files should from relative paths"

        # find group
        target, group = self.parse_targ_group()
        if not target in self.proj.targets.target_names:
            self.add_target()
        idx = self.proj.targets.target_names.index(target)
        targ = self.proj.targets.targets[idx]
        if not group in targ.groups.group_names:
            self.add_group()
        idx = targ.groups.group_names.index(group)
        g = targ.groups.groups[idx]

        for fn in glob.glob(proj + "/" + ptrn):
            fn = os.path.relpath(fn, proj)
            if not os.path.isfile(fn):
                continue
            print(f"\033[38;5;10madding source file {fn}\033[0m")

            if not fn.rpartition(".")[2] in ("c", "cpp", "s", "cxx", "S"):
                print(f"\033[38;5;9mskip: {fn} for wrong suffix\033[0m")
                continue

            if os.path.commonpath((os.path.abspath(fn), stub)) == stub:
                fn2 = self.fn2proj(self.args, fn)
                copy_file(fn, fn2)
                fn = os.path.normpath(os.path.relpath(fn2, proj))

            has_file = False
            for f in g.files.files:
                if os.path.commonpath((f.path, fn)) == fn:
                    has_file = True
                    break
            if has_file:
                print(f"\033[38;5;9mskip: {fn} already exists\033[0m")
                continue

            g.files.add_file(f".{os.path.sep}{fn}")

        self.write_proj(False)

    def add_inc(self): ...


def stub():
    mani = Manipulator(parse_args())
    match mani.args["option"]:
        case "gen_stub":
            mani.gen_stub()
        case "status":
            mani.status()
        case "sync_stub":
            mani.sync_stub()
        case "add_group":
            mani.add_group()
        case "add_target":
            mani.add_target()
        case "add_src":
            mani.add_src()
        case "add_inc":
            mani.add_inc()
        case "nop":
            mani.write_proj()
        case _:
            raise RuntimeError("unreachable")


if __name__ == "__main__":
    stub()
