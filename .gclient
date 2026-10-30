# Lets depot_tools (gn, autoninja) locate src/. Never `gclient sync` here: src/
# comes from the release tarball, see scripts/fetch-source.sh.
solutions = [{
  "name": "src",
  "url": None,
  "managed": False,
  "custom_deps": {},
  "custom_vars": {},
}]
target_os = ["android"]
