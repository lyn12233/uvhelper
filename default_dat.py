import lzma, base64


def compress(data: bytes) -> bytes:
    return base64.b64encode(lzma.compress(data))


def decompress(data: bytes) -> bytes:
    return lzma.decompress(base64.b64decode(data))


stmx_conf_h_defaults: dict[str, bytes] = {
    "stm32f10x": (
        b"/Td6WFoAAATm1rRGAgAhARYAAAB0L+Wj4A8+BHFdABeKrBoKYHEi5DjzuxbBgQbYh"
        b"F5LdwVtfmfFJlKp82qMO2OzEX3POk5YJ6mRWn16Knx9m/Xfqw4Tv8Gx77sdOuvgoa"
        b"ze07zJANURDAuqeLlMXH1RmEYL4iBY9WXgWo6cM01f7kqBXm1H7P8QiLUcE9ZTgbj"
        b"7l5feW5mR7ldgocpacnrT2MMr4vtltU3pFChBWl/a3hdftiXYjNpM0oEEx1u86gBd"
        b"JQKrh4u+89ik5orzqYSBcjJRs6fLBqI7uu3vDQ/9GCLUVce9tptsY7BFn4dxAbnug"
        b"cmTtPCHknneGX+jH+WaDh/E3bY+oYNDv1tLuzhtB/YvyOWiXE6pBZdzc7F1ejwVJK"
        b"M+rvvFLM/KVoUP66Fetx5ZiVlQG/g+aneWp1xo9SZv3p+NcGCxxDYkrN6NWdz+E1W"
        b"l9ng2Fx8R+LRIhEX43vU87n4FuqflLHmkAgLEqrr6t5VG1O8Tmg0Z8RQZVfS1MF83"
        b"2q33EreLhGlxLPUK04uAIxiYbOoeplKA//G79dLcm5mcnNJZBv5xBa1CZPHpdCb0F"
        b"0vd6O0MU4lW8cVPrI3LSj1CkhU5Pt4rzArkwU0ykueK0wI4gPobMG/0yk9nJlqB8a"
        b"hDggN8HUsRIvv3fOOVo4VRKlgw2wDBfFrE6zKW/T+vjnsw2Ak+QxoKZ7f2qVq4Fyl"
        b"fT3F/Qrs+tkXZGZ0zOM+vcDuSbgFD9mzVfShavLRP9aVwiVpRRrZ1Cx1lyhFJ+7CG"
        b"XWI/xRCTvVjABunoamJu9NMtpwRhLRSo62kGW6/wQYKFNR8bGKiA51e5esXra1fls"
        b"h3ejObR1Fy+/0enQYUnD69wad73XehFIoCoFFb4kWAVf3GFvkn6uS1/934SRP9i0M"
        b"uwBMkHufGSDtz4eURyXW/vohk92LmNDD3fEXbgKJpz+nd7apBNRDi9rb/loUe77Or"
        b"1HUYn3Y0VNB3pHUdbAugGNqJmHcSmJjs1HM7a9BuPJJpuzh7U3g4kf0K+l7DyZOiO"
        b"Z4lpXun5jka2dr8Up8DTkBKal5tNZV3q5IjENq+c8fyxAIXeE2p7WM62cWc3Vmxh8"
        b"rNUucExtYERNNM2hArdh5aCwqFjN30rW6dmEke4E+oAMKX8fmeBpNAimAJPeXv5BG"
        b"0OSztABqB3HV0cng2dhGWrb9dN9dJMtU1lPzoQI8Op+YCRcPNWIJhWeDZRhMHs2jE"
        b"nLnHutlFEkRHW3PfeQcql+w4LIiO+ORzIkcm5t/mZjrdNIJkFWTb/YGQ+S1/BmgMP"
        b"RUp2QuwQyPBLPJ6kypE6V8SywU5sfrZaWcPZCS7k0O4EXuGzaBTh2ASXvcoBG4Avd"
        b"F1sroJrkNoE7YS1N798uoNtXJWeOtzahx00ZRiBUxBfTdtSY606y7Zt3u9b48iWYw"
        b"6aMMPDJM16i2U9yZfM5j9crmjRs3BC6+NaWxUu3AUEIhQXbM9vipKODlr3aTjNgmG"
        b"I2FwFag+Xgrt6mHHYx8lJ53TO645OPd5OMz9Lvg3BK5LVdptMP13tliFzhwNkAAAA"
        b"AAAaAlPeX9TxEwABjQm/HgAAHGHCP7HEZ/sCAAAAAARZWg=="
    )
}

rte_conf_h_defaults: str = (
    "#ifndef RTE_COMPONENTS_H\n"
    "#define RTE_COMPONENTS_H\n"
    '#define CMSIS_device_header "{}.h"\n'
    "#endif\n"
)
