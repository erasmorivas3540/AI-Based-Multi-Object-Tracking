#!/usr/bin/env bash
# Step 2: Gazebo Harmonic runs and a camera sensor publishes images.
set -u
pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1"; FAILED=1; }
FAILED=0

echo "== Step 2: Gazebo Harmonic =="

if ! command -v gz >/dev/null; then
  fail "'gz' command not found — install ros-jazzy-ros-gz (pulls in Harmonic)"
  exit 1
fi
VER=$(gz sim --versions 2>/dev/null | head -n1)
echo "  gz sim version: ${VER:-unknown}"
case "$VER" in 8.*) pass "Gazebo Harmonic (gz-sim 8.x)";; *) fail "Expected gz-sim 8.x (Harmonic), got '$VER'";; esac

echo "  Launching sensors demo headless (-s -r) for 15 s..."
gz sim -s -r sensors_demo.sdf >/tmp/gz_smoke.log 2>&1 &
GZ_PID=$!
sleep 10
if gz topic -l 2>/dev/null | grep -qi "camera"; then
  pass "camera topic present: $(gz topic -l | grep -i camera | head -n1)"
else
  fail "no camera topic (see /tmp/gz_smoke.log; world name may differ in your install)"
fi
kill $GZ_PID 2>/dev/null; wait $GZ_PID 2>/dev/null

echo
echo "Note: headless (-s) still needs a working renderer for camera sensors."
echo "If cameras fail headless on your machine, run with the GUI once to confirm."
exit $FAILED
