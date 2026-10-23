#!/usr/bin/env bash
# Step 3: ros_gz_bridge delivers Gazebo camera images to a ROS 2 topic.
set -u
source /opt/ros/jazzy/setup.bash
pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1"; FAILED=1; }
FAILED=0

echo "== Step 3: Gazebo -> ROS 2 bridge =="

gz sim -s -r sensors_demo.sdf >/tmp/gz_bridge.log 2>&1 &
GZ_PID=$!
sleep 8

GZ_CAM=$(gz topic -l 2>/dev/null | grep -i camera | grep -vi info | head -n1)
if [ -z "$GZ_CAM" ]; then
  fail "no Gazebo camera topic; fix step 2 first"
  kill $GZ_PID 2>/dev/null; exit 1
fi
echo "  bridging $GZ_CAM"

ros2 run ros_gz_bridge parameter_bridge "${GZ_CAM}@sensor_msgs/msg/Image[gz.msgs.Image" >/tmp/bridge.log 2>&1 &
BR_PID=$!
sleep 4

RATE=$(timeout 8 ros2 topic hz "$GZ_CAM" 2>/dev/null | grep "average rate" | tail -n1)
if [ -n "$RATE" ]; then
  pass "ROS topic $GZ_CAM receiving images ($RATE)"
else
  fail "no images on ROS side (check /tmp/bridge.log, message mapping, topic name)"
fi

kill $BR_PID $GZ_PID 2>/dev/null; wait 2>/dev/null
exit $FAILED
