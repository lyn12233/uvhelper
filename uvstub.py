import argparse
from typing import Literal
import os
import glob
from collections import defaultdict
import xml.etree.ElementTree as ET
from warnings import warn
from concurrent.futures import ThreadPoolExecutor
import json

from .uvconfig import UVProject
from .uvstrap import copy_file, run_command

type args_t = dict[Literal["option", "project_dir", "stub_dir"], str]


def parse_args() -> args_t:

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "option",
        choices=["gen_stub", "sync_stub", "nop"],
        help="operation to perform with stub",
    )
    parser.add_argument(
        "--project_dir", type=str, default=".", help="directory of the project"
    )
    parser.add_argument(
        "--stub_dir", type=str, default="./stub", help="directory of the stub files"
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

    return {
        "option": res.option,
        "project_dir": os.path.normpath(os.path.abspath(res.project_dir)),
        "stub_dir": os.path.normpath(os.path.abspath(res.stub_dir)),
    }


class Manipulator:
    proj: UVProject
    args: args_t
    links: list[tuple[str, str]]

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
        # collect headers
        for inc in self.collect_includes().values():
            for paths in inc.values():
                for p in paths:
                    if os.path.isdir(p):
                        for fn in glob.glob(os.path.join(p, "**", "*"), recursive=True):
                            if os.path.isfile(fn):
                                files.add(fn)
                    elif os.path.isfile(p):
                        files.add(p)
        # collect markdowns
        mds = glob.glob(self.args["project_dir"] + "/*.md") + glob.glob(
            self.args["project_dir"] + "/**/*.md"
        )
        mds = [f for f in mds if not "uvhelper" in f and not "stub" in f]
        print(f"markdowns: {mds}")
        # input()
        for md in mds:
            self.links.append((md, self.fn2stub(self.args, md)))
        # files.update(mds)
        print(f"collected files: {len(files)}")
        # get links
        for fn in files:
            fn = os.path.normpath(os.path.abspath(fn))
            if (
                os.path.commonpath([self.args["project_dir"], fn])
                != self.args["project_dir"]
            ):
                print(f"\033[38;5;9mgen_stub: skip {fn}\033[0m")
                continue
            stub_fn = self.fn2stub(self.args, fn)
            self.links.append((fn, stub_fn))
        # print(self.links)
        # input()

    def gen_stub(self):
        #
        # update links
        self.collect_links()

        # copy files
        with ThreadPoolExecutor() as e:
            for fn, stub_fn in self.links:
                e.submit(copy_file, fn, stub_fn)

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

            # commandline amendments
            # use armclang
            c_defines += ["__ARMCC_VERSION=6230050", "__ARM_COMPAT_H"]
            a_defines += ["__ARMCC_VERSION=6230050", "__ARM_COMPAT_H"]

            for group in targ.groups.groups:
                for file in group.files.files:
                    output = os.path.splitext(file.path)[0] + ".obj"
                    cmds.append(
                        {
                            "directory": self.args["stub_dir"],
                            "command": f"clang "
                            f'{" ".join(["-I"+inc for inc in (a_inc if file.path.endswith(".s")else c_inc)])} '
                            f'{" ".join(["-D"+defs for defs in (a_defines if file.path.endswith(".s")else c_defines)])}'
                            f"-o {output} -c {file.path}",
                            "file": file.path,
                            "output": output,
                        }
                    )
        print("generating compile_commands.json")
        with open(
            self.args["stub_dir"] + "/compile_commands.json", "w", encoding="utf-8"
        ) as f:
            json.dump(cmds, f, indent=4)

    def sync_stub(self): ...


def stub():
    mani = Manipulator(parse_args())
    match mani.args["option"]:
        case "gen_stub":
            mani.gen_stub()
        case "sync_stub":
            mani.sync_stub()
        case _:
            pass


if __name__ == "__main__":
    stub()
