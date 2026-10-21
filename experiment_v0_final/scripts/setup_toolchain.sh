#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
mkdir -p "$TOOLCHAIN_HOME" "$ROOT/logs"
if [[ ! -d "$REACTOR_UC_PATH/.git" ]]; then
    git clone --no-checkout https://github.com/lf-lang/reactor-uc.git "$REACTOR_UC_PATH"
    git -C "$REACTOR_UC_PATH" checkout --detach "$REACTOR_UC_COMMIT"
fi
[[ $(git -C "$REACTOR_UC_PATH" rev-parse HEAD) == "$REACTOR_UC_COMMIT" ]] || {
    echo 'Unexpected runtime commit; refusing to overwrite an existing checkout.' >&2
    exit 1
}
git -C "$REACTOR_UC_PATH" submodule update --init external/nanopb
if [[ ! -x "$ULFC" ]]; then
    (cd "$REACTOR_UC_PATH/ulf" && ./gradlew --no-daemon --max-workers=2 assemble :cli:lfc:assemble) \
        2>&1 | tee "$ROOT/logs/toolchain_build.txt"
fi
if [[ ! -x "$ANALYSIS_PYTHON" ]] || ! "$ANALYSIS_PYTHON" -m pip --version >/dev/null 2>&1; then
    # --without-pip also works on Ubuntu installations without python3-venv.
    python3 -m venv --without-pip "$TOOLCHAIN_HOME/venv"
    curl -fL https://bootstrap.pypa.io/get-pip.py -o "$TOOLCHAIN_HOME/get-pip.py"
    "$ANALYSIS_PYTHON" "$TOOLCHAIN_HOME/get-pip.py"
fi
"$ANALYSIS_PYTHON" -m pip install -r "$ROOT/requirements.txt"
{
    "$ULFC" --version
    git -C "$REACTOR_UC_PATH" rev-parse HEAD
    git -C "$REACTOR_UC_PATH" submodule status
    "$ANALYSIS_PYTHON" -m pip freeze
} | tee "$ROOT/logs/toolchain_versions.txt"
