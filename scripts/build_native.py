"""Build the C ABI library without copying a developer's precompiled binary."""
import pathlib
import shutil
import subprocess
import sys
import os

root = pathlib.Path(__file__).resolve().parents[1]
out = root / 'src/hybrid_quant/_native'
out.mkdir(exist_ok=True)
extension = '.dll' if sys.platform == 'win32' else '.dylib' if sys.platform == 'darwin' else '.so'
compiler = shutil.which('g++') or shutil.which('clang++')
if sys.platform == 'win32':
    vswhere = pathlib.Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if vswhere.exists():
        install = subprocess.check_output([str(vswhere), '-latest', '-products', '*',
            '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
            '-property', 'installationPath'], text=True).strip()
        if install:
            setup = pathlib.Path(install) / 'Common7/Tools/VsDevCmd.bat'
            cmd = (f'call "{setup}" -arch=x64 -host_arch=x64 >nul && '
                   f'cl /nologo /std:c++14 /O2 /EHsc /LD /I"{root / "cpp/include"}" '
                   f'"{root / "cpp/src/core.cpp"}" /link /OUT:"{out / "hybrid_quant_core.dll"}"')
            subprocess.run(cmd, shell=True, executable=os.environ.get('COMSPEC', 'cmd.exe'), cwd=out, check=True)
            print('Built with MSVC x64:', out)
            raise SystemExit(0)
if not compiler:
    raise SystemExit('Install GCC or Clang with C++14 support and add it to PATH.')
flags = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared']
subprocess.run([compiler, '-std=c++14', '-O2', '-Wall', '-Wextra', '-fPIC', *flags,
                '-I', str(root / 'cpp/include'), str(root / 'cpp/src/core.cpp'),
                '-o', str(out / ('hybrid_quant_core' + extension))], check=True)
print('Native core built:', out)
