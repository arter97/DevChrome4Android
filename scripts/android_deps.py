#!/usr/bin/env python3
"""Fetch the Android-only DEPS that the official (Linux) source tarball omits.

No git history is downloaded: git deps are fetched as gitiles tarballs,
CIPD deps via `cipd ensure`, GCS deps as plain objects.

Usage: android_deps.py [--list] SRC_DIR
"""
import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEPOT_TOOLS = os.path.join(os.path.dirname(HERE), 'depot_tools')
sys.path.insert(0, DEPOT_TOOLS)
import gclient  # noqa: E402
import gclient_eval  # noqa: E402


def builtin_vars(target_os):
  v = {f'checkout_{o}': o in target_os for o in (
      'android', 'chromeos', 'fuchsia', 'ios', 'linux', 'mac', 'win')}
  for cpu in ('arm', 'arm64', 'x86', 'mips', 'mips64', 'ppc', 'riscv64',
              's390', 'x64', 'loong64'):
    v[f'checkout_{cpu}'] = cpu in ('arm', 'arm64', 'x64')
  v['host_os'] = 'linux'
  v['host_cpu'] = 'x64'
  return v


def load_deps(src):
  with open(os.path.join(src, 'DEPS')) as f:
    content = f.read()
  scopes = {}
  for name, oses in (('android', ['android', 'linux']), ('linux', ['linux'])):
    bv = builtin_vars(oses)
    local = gclient_eval.Exec(content, 'DEPS', builtin_vars=bv)
    variables = dict(local.get('vars', {}))
    variables.update(bv)
    scopes[name] = (local, variables)
  return scopes


def active(dep, variables):
  cond = dep.get('condition')
  return not cond or gclient_eval.EvaluateCondition(cond, variables)


def android_only(scopes):
  (a_local, a_vars), (_, l_vars) = scopes['android'], scopes['linux']
  for path, dep in a_local['deps'].items():
    if isinstance(dep, str):
      dep = {'url': dep, 'dep_type': 'git'}
    path = path.removeprefix('src/')
    if active(dep, a_vars) and (not active(dep, l_vars) or
                                path in PRUNED_SHARED):
      yield path, dep


# Test-only or emulator payloads that a device build never needs.
SKIP_PATHS = {'android_webview/tools/cts_archive/cipd'}
SKIP_PACKAGES = ('/emulator', '/system_images/')


# Deps shared with Linux that the tarball exporter prunes, keyed by a file the
# Android build needs. They are re-fetched when that file is missing.
PRUNED_SHARED = {'third_party/jdk/current': 'bin/javac'}


def cipd_version(src, pkg):
  if 'version_file' in pkg:
    with open(os.path.join(src, pkg['version_file'])) as f:
      return f.read().strip()
  return pkg['version']


def is_empty(path):
  return not os.path.isdir(path) or not os.listdir(path)


def fetch_git(src, path, url):
  repo, rev = url.split('@')
  dest = os.path.join(src, path)
  if not is_empty(dest):
    print(f'  [skip] {path} (present)')
    return
  arc = f'{repo.removesuffix(".git")}/+archive/{rev}.tar.gz'
  print(f'  [git ] {path} <- {arc}')
  os.makedirs(dest, exist_ok=True)
  with urllib.request.urlopen(arc) as r, \
      tarfile.open(fileobj=r, mode='r|gz') as t:
    t.extractall(dest, filter='tar')


def fetch_gcs(src, path, dep, variables=None, force=False):
  dest = os.path.join(src, path)
  for obj in dep['objects']:
    if variables is not None and not active(obj, variables):
      continue
    stamp = os.path.join(dest, '.' + obj['object_name'].replace('/', '_'))
    if os.path.exists(stamp) and not force:
      continue
    url = f'https://storage.googleapis.com/{dep["bucket"]}/{obj["object_name"]}'
    print(f'  [gcs ] {path} <- {url}')
    os.makedirs(dest, exist_ok=True)
    with tempfile.NamedTemporaryFile() as tmp:
      subprocess.check_call(['curl', '-sSfL', '-o', tmp.name, url])
      out = subprocess.check_output(['sha256sum', tmp.name]).split()[0]
      assert out.decode() == obj['sha256sum'], f'sha256 mismatch for {url}'
      if tarfile.is_tarfile(tmp.name):
        with tarfile.open(tmp.name) as t:
          t.extractall(dest, filter='tar')
      else:
        subprocess.check_call(['cp', tmp.name,
                               os.path.join(dest, obj.get('output_file') or
                                            os.path.basename(obj['object_name']))])
    open(stamp, 'w').close()


def write_gclient_args(src, scopes):
  """Regenerates build/config/gclient_args.gni like `gclient runhooks`."""
  local, variables = scopes['android']
  lines = ["# Generated from 'DEPS'"]
  for name in local['gclient_gn_args']:
    value = variables[name]
    if isinstance(value, gclient_eval.ConstantString):
      value = value.value
    elif isinstance(value, str):
      value = gclient_eval.EvaluateCondition(value, variables)
    lines.append(f'{name} = {gclient.ToGNString(value)}')
  with open(os.path.join(src, local['gclient_gn_args_file'].removeprefix('src/')),
            'w') as f:
    f.write('\n'.join(lines) + '\n')


CLANG_DIR = 'third_party/llvm-build/Release+Asserts'


def fix_clang(src, scopes):
  """The tarball ships clang with a blanked cr_build_revision; refetch it."""
  want = subprocess.check_output(
      [sys.executable, '-c', 'import update; print(update.PACKAGE_VERSION)'],
      cwd=os.path.join(src, 'tools/clang/scripts'), text=True).strip()
  stamp = os.path.join(src, CLANG_DIR, 'cr_build_revision')
  have = open(stamp).read().strip() if os.path.exists(stamp) else ''
  if have == want:
    return
  print(f'  [clang] cr_build_revision {have!r} != {want!r}, refetching')
  local, variables = scopes['android']
  fetch_gcs(src, CLANG_DIR, local['deps']['src/' + CLANG_DIR], variables,
            force=True)
  have = open(stamp).read().strip()
  assert have == want, f'clang still at {have!r}, expected {want!r}'


def main():
  p = argparse.ArgumentParser()
  p.add_argument('--list', action='store_true')
  p.add_argument('src')
  args = p.parse_args()
  src = os.path.abspath(args.src)
  scopes = load_deps(src)
  deps = list(android_only(scopes))
  write_gclient_args(src, scopes)
  if args.list:
    for path, dep in deps:
      t = dep.get('dep_type', 'git')
      what = dep.get('url') if t == 'git' else (
          [f'{x["package"]}@{x.get("version", dict(x))}' for x in dep.get('packages', [])]
          if t == 'cipd' else dep.get('bucket'))
      state = 'empty' if is_empty(os.path.join(src, path)) else 'present'
      print(f'{t:5} {state:8} {path} {what}')
    return

  ensure = ['$ParanoidMode CheckPresence', '']
  for path, dep in deps:
    t = dep.get('dep_type', 'git')
    if path in SKIP_PATHS:
      continue
    if t == 'git':
      fetch_git(src, path, dep['url'])
    elif t == 'gcs':
      fetch_gcs(src, path, dep)
    elif t == 'cipd':
      sentinel = PRUNED_SHARED.get(path)
      if sentinel and not os.path.exists(os.path.join(src, path, sentinel)):
        print(f'  [cipd] {path} is pruned (no {sentinel}), replacing')
        shutil.rmtree(os.path.join(src, path), ignore_errors=True)
      ensure.append(f'@Subdir {path}')
      for pkg in dep['packages']:
        if not any(x in pkg['package'] for x in SKIP_PACKAGES):
          ensure.append(f'{pkg["package"]} {cipd_version(src, pkg)}')
      ensure.append('')
  fix_clang(src, scopes)
  ensure_file = os.path.join(src, '.android_deps.ensure')
  with open(ensure_file, 'w') as f:
    f.write('\n'.join(ensure))
  print(f'  [cipd] ensuring {sum(1 for l in ensure if l.startswith("@Subdir"))} '
        'package dirs')
  subprocess.check_call([os.path.join(DEPOT_TOOLS, 'cipd'), 'ensure',
                         '-root', src, '-ensure-file', ensure_file])


if __name__ == '__main__':
  main()
