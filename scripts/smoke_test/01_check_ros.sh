#!/usr/bin/env bash
# Step 1: Ubuntu 24.04 + ROS 2 Jazzy are installed and can pass a message.
set -u
pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1"; FAILED=1; }
FAILED=0

echo "== Step 1: OS and ROS 2 =="

if grep -q 'VERSION_ID="24.04"' /etc/os-release 2>/dev/null; then
  pass "Ubuntu 24.04"
else
  fail "Not Ubuntu 24.04 ($(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2))"
fi

if [ -f /opt/ros/jazzy/setup.bash ]; then
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash
  pass "ROS 2 Jazzy found at /opt/ros/jazzy"
else
  fail "/opt/ros/jazzy/setup.bash missing — install ros-jazzy-desktop"
  exit 1
fi

echo "  Running talker/listener for 5 seconds..."
timeout 5 ros2 run demo_nodes_cpp talker >/dev/null 2>&1 &
OUT=$(timeout 5 ros2 run demo_nodes_py listener 2>&1)
if echo "$OUT" | grep -q "I heard"; then
  pass "talker -> listener message received"
else
  fail "listener heard nothing (check ros-jazzy-demo-nodes-cpp/py, ROS_DOMAIN_ID, firewall)"
fi

echo
echo "Record in docs/versions.md:"
echo "  ROS_DISTRO=$ROS_DISTRO"
echo "  RMW: ${RMW_IMPLEMENTATION:-default (check 'ros2 doctor --report')}"
exit $FAILED
