# Draft message to advisor

**Subject:** AI-Based Multi-Object Tracking — 6-week plan and two scope questions

Dr. ___,

I've mapped the micro-plan onto a six-week schedule (attached: concise plan and
the 6-week scope). All eight steps are covered. Step 6 (occlusion/degraded
visibility) becomes the research question: whether a small calibrated learned
score recovers lost identities better than a matched hand-tuned rule when the
camera is moving.

Two questions before I lock in Week 1:

1. **MMTracking.** I've planned it as optional because its dependencies conflict
   with the ROS 2 stack, and I'd compare against ByteTrack and BoT-SORT directly.
   Do you want MMTracking used specifically, or is any solid comparison fine?

2. **Collision avoidance.** The system works in camera-image coordinates, so it
   provides local awareness but not metric distances. Should I treat separation
   and collision avoidance as the motivating application (future work), or do
   you expect a demonstration of it within the six weeks? The second would need
   depth or range estimation.

Week 1 deliverables: environment working end to end, related-work matrix and
novelty note, a minimal Gazebo scene, and a verified evaluation pipeline.

Thank you,
Erasmo
