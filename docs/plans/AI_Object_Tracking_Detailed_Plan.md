<!-- Text of AI_Object_Tracking_Detailed_Plan.docx (16 October 2026), the original 12-week plan. Section numbers cited in code and docs (e.g. "plan section 16") refer to this file. The 6-week scope that supersedes its schedule is docs/scope_6week.md. -->

# AI-Augmented Object Tracking — Detailed Research Plan

AI-Based Multi-Object Tracking for Autonomous Multi-Drone Operations

## 1. Purpose, scope and intended contribution

This proposal develops a real-time perception prototype that detects unmanned aerial vehicles (UAVs) and ground vehicles, maintains camera-local identities, and forecasts their short image-plane trajectories. Artificial intelligence (AI) augments a conventional tracker through a small learned identity-recovery model. The model estimates whether a newly detected object belongs to a recently lost track after temporary occlusion or poor image quality.

The central research question is: can an observable-feature recovery model improve correct identity restoration under simultaneous camera motion and interrupted visibility, at a controlled false-recovery rate and within a declared processing budget? The project uses existing research as an experimental scaffold. Its contribution must emerge from a precisely defined intervention and reproducible evidence; combining existing libraries alone is not an algorithmic novelty claim.

The working schedule is 12 weeks at 15–20 researcher hours per week. Core experiments use one moving observer and three to eight targets. A later demonstration runs two independent observer pipelines. “Multi-drone” therefore describes the operating setting and multiple perception streams; it does not imply that the prototype solves shared identities across cameras, distributed coordination, or autonomous flight control.

The intended output is a documented Robot Operating System 2 (ROS 2) perception pipeline, a controlled simulation dataset and evaluation protocol, baseline comparisons, a learned recovery component, and an evidence-based research report. A negative result remains useful if the method does not outperform a well-tuned control and the experiment identifies why.

This document specifies proposed work, assumptions and prospective success criteria. It contains no measured project results. Literature and official software documentation were checked through 16 October 2026. Recent preprints are identified as such; their reported performance is not treated as independently verified.

Reading guide: sections 2–6 establish concepts, research and assumptions; 7–14 specify architecture, software and interfaces; 15–23 define data, algorithms and experiments; 24–29 cover execution, resources, risks and deliverables; 30–33 provide glossary and references. The separate concise plan is the decision summary, while the ten-slide presentation is designed for discussion with the research group.

## 2. Concepts and a worked example

Detection answers “what is visible in this image and where?” A detector produces a class label, a confidence score and a bounding box: a rectangle enclosing the object. A detection does not, by itself, establish whether an object is the same object seen earlier. Detection confidence is also not automatically a calibrated probability of correct identity.

Multi-object tracking links detections across time. A track is the evolving record of one hypothesized object, including its identifier, recent positions and motion estimate. Identity association is the decision that a detection belongs to a particular track. An identity switch occurs when the tracker assigns the wrong continuing identity according to the evaluation convention. Fragmentation describes interruption of a previously tracked target. A false recovery can be more damaging than a brief missing track because it creates a confidently incorrect history.

Consider two visually similar UAVs crossing while the observer turns. UAV A has track 17 and UAV B has track 23. A passes behind a structure for one second. Its last known location becomes less reliable because both the target and camera move. When two detections appear nearby, simply selecting the closest rectangle can attach track 17 to B. The proposed model instead combines motion consistency, time since last observation, image quality and confidence history to estimate each candidate relationship. The assignment step must still enforce one detection per track and allow rejection of both candidates.

Occlusion means an object is hidden behind another surface. Degraded visibility also includes motion blur, small apparent size and poor contrast. These causes are related but different; the experiment varies occlusion duration and blur separately. A target leaving the camera field of view is a different event from a target temporarily hidden inside it, so the primary recovery protocol treats them separately.

A trajectory forecast estimates future positions from past and current observations. Here those positions are normalized image coordinates, not distances in metres. If an object grows in the image, it may be approaching, rotating, or being viewed through a changed camera pose. A monocular box does not uniquely resolve depth.

The tracker may temporarily publish a predicted-only state during missing observations. That state must be labelled and its uncertainty allowed to increase. It must not be presented as a current visual detection. This distinction matters both for honest evaluation and for any later system consuming the output for awareness.

## 3. Research scaffold and originality boundary

ByteTrack (2022) associates detections at different confidence levels and supplies the main tracking-by-detection foundation. Its native implementation already supports lost tracks and recovery; adding a lost-track stage is therefore not itself new. BoT-SORT (2022) supplies a comparator incorporating motion, appearance and camera-motion compensation. These methods establish strong controls rather than disposable starting points. [1, 2]

DroneMOT (2024) motivates drone-specific stressors such as small targets, viewpoint changes, blur and concurrent observer and target motion. TrackTrack (2025) provides a more recent online tracking comparator with track-oriented association and initialization. Its required detector information must be preserved when reproducing its native configuration. [3, 4]

DMTrack (2025 preprint), DynUAV (2026) and JitTrack (2026 preprint) demonstrate that learned motion, dynamic aerial scenes and camera instability are active research areas. They are important overlap checks. Their existence rules out a broad claim that this project invents motion-aware or uncertainty-aware drone tracking. The week-one audit must compare the proposed intervention with the actual methods, not just paper titles or abstracts. [5–7]

The proposed narrow contribution is a calibrated, lightweight lost-track recovery score using inference-time observable features, evaluated through a fixed event protocol under controlled combinations of camera motion, occlusion and blur. Three possible contributions are separated: a recovery algorithm if a substantive methodological difference survives review; an experimental contribution through matched controls and transparent event scoring; and a systems contribution through reproducible ROS 2 integration with measured latency.

Create a related-work matrix with fields for task, sensors, input detections, motion model, association cost, recovery/lifecycle logic, camera-motion estimation, uncertainty treatment, benchmarks, compute, released code and stated limitations. Record publication status and exact implementation revision. Read the method and ablation sections of the closest papers and inspect public code where available.

The novelty decision is a week-one gate. If an existing method implements the same score and recovery mechanism, reproduce that mechanism and reposition the project around the controlled empirical question or select a demonstrably different, feasible intervention. Do not rename an existing method and call it original. The final paper should explain exactly which code and concepts were reused, which component changed, and which claim is supported by the measurements.

## 4. Questions, hypotheses and decision rules

The primary question concerns identity recovery, not detector accuracy alone. Hold detector outputs and the ordinary active-track association fixed when testing the new recovery score. This isolates the effect of deciding which recently lost identity to restore. Also report native end-to-end baselines because an isolated intervention comparison does not describe the best complete existing system.

H1 — recovery reliability: at a validation-selected operating point intended to achieve at least 95% recovery precision, the learned score will increase recovery recall relative to the matched hand-designed recovery control on held-out flights. Precision is the proportion of claimed recoveries that are correct; recall is the proportion of eligible ground-truth recovery events successfully recovered. The 95% threshold is a proposed application preference, not a prior result or universal safety requirement.

H2 — useful information: adding estimated camera-motion quality and observable image-quality features will improve recovery beyond detection confidence and basic geometric motion features. Test this through feature-group ablations that use the same data partitions, candidate gates and training budget. If removing the feature group has no consistent effect, do not claim that it explains the improvement.

H3 — practical integration: the additional recovery logic can operate within a real-time pipeline on the declared workstation. The proposed system targets are 20 frames per second per observer, 40 aggregate frames per second with two observers, and less than 100 milliseconds at the 95th percentile from image availability to track publication. These are targets to test, not promised performance. Report recovery-stage overhead separately.

Choose thresholds and model size on the validation set. Freeze the primary hypotheses, metrics, candidate rules and test manifest before the final held-out evaluation. If a setting cannot meet the validation precision target, report that failure and compare precision–recall curves; do not silently relax the target after seeing test results. The observed test precision can be lower than the validation target and must be reported with uncertainty.

Primary evidence is the paired difference in event recovery recall with its confidence interval and the achieved recovery precision. Whole-sequence identity metrics and latency are supporting constraints. A convincing result improves recovery without material identity degradation or excessive runtime cost. A result that helps only easy simulated cases, increases false associations, or depends on simulator-only information does not support the intended claim.

## 5. Assumptions register: research and data

A01 — available effort. Assume one researcher can allocate 15–20 hours weekly for 12 weeks, approximately 180–240 hours. This supports a focused extension and evaluation rather than a new detector, simulator and flight controller. Confirm effort at kickoff. If availability drops, retain the recovery study and reduce optional demonstrations before reducing baseline rigor.

A02 — reusable assets. Assume usable UAV, vehicle, camera and environment models already exist or can be obtained with appropriate usage rights. Validate rendering, motion and annotation access in week two. If assets require extensive repair, reduce environment variety and document the limitation; do not count modelling time as algorithm development.

A03 — a known camera. Assume image dimensions, projection parameters and timestamps are available from simulation. Validate box projection and frame alignment against rendered images. Incorrect calibration corrupts labels and camera-motion interpretation, so this is a blocking data-quality issue.

A04 — target count and classes. Assume three to eight targets are enough to create crossings, ambiguity and temporary disappearance within the initial compute budget. Use UAV and ground-vehicle scenario groups. The study will not establish performance in very dense crowds, with dozens of objects, or for every aircraft category.

A05 — learnable synthetic cues. Assume training data contain sufficient variation to learn recovery relationships rather than memorized layouts. Test held-out layouts, trajectories and seeds, and inspect feature distributions. If a model learns scene identity or renderer artifacts, remove those cues and narrow the claim to the tested distribution.

A06 — reliable simulation truth. Assume simulator identities and object geometry can be aligned to image frames. Keep truth in a separate recording/evaluation path. Audit projection, occlusion labels and identity continuity manually before scale-up. An annotation bug can produce an apparent tracking improvement, so audit labels before debugging the model.

A07 — representative stress factors. Assume camera motion, occlusion duration and blur are practical proxies for important aerial tracking difficulties. These do not fully represent weather, rolling-shutter distortion, sensor noise, low illumination or real drone vibration. Report them as controlled factors rather than a complete model of real flight.

A08 — limited transfer claim. Assume a small licensed real-video sanity check may be possible in week eleven. It is optional and must not become a hidden requirement for completing the simulation study. Without suitable real data, claim simulation evidence only; a qualitative video overlay alone does not establish generalization.

## 6. Assumptions register: geometry and operation

A09 — camera-local identities. An identity is unique only within one observer stream and run. The public key is observer identifier plus local track identifier, with a run identifier where records are combined. Two cameras may assign different identities to the same physical UAV. Shared identity fusion would require cross-camera correspondence, synchronization and geometry that are outside the core scope.

A10 — image-plane prediction. The core motion state describes normalized image position and velocity. Constant velocity is an approximation over 0.5 and 1.0 second horizons, especially during camera turns. Measure forecast error by motion regime; do not convert these predictions into metres without an independently justified depth model.

A11 — finite recovery window. Assume gaps of up to two seconds are relevant for the primary study. Candidate lifetimes and event definitions must be aligned and frozen on validation. Longer disappearances, exit/re-entry and object births remain secondary analyses. Extending lifetime can increase false matches, so it is not a free improvement.

A12 — workstation execution. Assume access to a compatible graphics processing unit (GPU) and enough memory for detector training and inference. The project is not initially an embedded deployment study. Publish hardware, input resolution, model size and precision mode with every runtime claim; workstation throughput does not imply onboard feasibility.

A13 — stable software environment. Use Ubuntu 24.04, ROS 2 Jazzy and Gazebo Harmonic as a documented compatible starting pair, subject to a week-one installation smoke test. These are deliberate environment choices, not a claim that they are the newest releases. Exact Python, PyTorch, detector and accelerator versions must be selected together and frozen after testing. [9]

A14 — sensor delivery can fail. Camera frames may arrive late, be dropped or be duplicated. Algorithms must use timestamps and reject invalid ordering. Latency measurements distinguish simulated sensor time from wall-clock elapsed time. A simulation running slower than real time cannot be used to claim real-time performance solely from its nominal frame rate.

A15 — perception support, not flight authority. The prototype provides local object awareness and traceable uncertainty. Separation or collision-avoidance decisions would additionally need metric relative state, decision logic and independent validation. The proposed demonstration does not establish a collision-free controller.

A16 — thresholds are empirical. Confidence cutoffs, geometric gates, noise settings and minimum object sizes are not known optimal values in advance. Tune them using development data, document the search budget and freeze them before test. Whenever a practical assumption fails, record the change and its effect on the claim rather than silently changing the protocol.

## 7. Architecture, coordinates and time

The core data path is: Gazebo camera images enter ROS 2 through the Gazebo bridge; a detector produces object boxes; a tracker performs ordinary association and recovery; a predictor produces short future image positions; publishers expose tracks and forecasts to visualization, recording and evaluation. Ground-truth labels travel through a separate evaluation path and are unavailable to the inference nodes.

Use an explicit image convention. Pixel x increases to the right and pixel y increases downward, with image dimensions W and H. A box is stored as centre x, centre y, width and height, or converted through a documented adapter from corner coordinates. Normalized centre coordinates are u = x/W and v = y/H. Track motion uses elapsed seconds, so velocities are expressed as normalized image units per second. Never mix a resized detector image with original-image coordinates without an inverse transform.

Image-plane covariance describes uncertainty in this same coordinate system. If a geometric extension is added, keep camera-frame and world-frame quantities in separate message types with explicit frame identifiers and units. The transformation library tf2 manages coordinate-frame relationships; it does not infer missing depth or camera pose. [22]

Use the source image timestamp as the reference time for a detection and its track update. Record arrival and publication wall-clock times separately using a monotonic clock for durations. A monotonic clock measures elapsed time without jumps caused by adjustments to the calendar clock. For bag replay, preserve source timestamps and record the replay rate. For live simulation, record its real-time factor: the ratio of simulated elapsed time to wall-clock elapsed time.

The initial tracker is single-threaded per stream for deterministic state updates. Detector execution can be shared or batched later, but track state must remain isolated by observer. If a frame is delayed, avoid processing it after a newer state without a deliberate out-of-sequence update mechanism. The initial implementation drops such stale frames, logs them and reports their frequency.

Failures should be visible. A missing camera calibration, invalid image encoding, inference exception or timestamp reversal produces a diagnostic event, not fabricated detections. A detector timeout can cause a predicted-only track update within the allowed age limit. Once that limit is reached, expire the track and publish its termination status if required by consumers.

## 8. Existing software: simulation and ROS 2

Ubuntu is the Linux operating system used to run the development environment. It supplies system libraries, device access and package installation. ROS 2 is Robot Operating System 2: despite its name, it is middleware and a collection of robotics tools running on the operating system. It organizes programs as nodes and exchanges typed messages over named topics. Jazzy is the selected ROS 2 distribution, a coordinated release of related packages.

Gazebo is the simulator. Harmonic is the selected Gazebo release. It generates the virtual world, target motion, camera images and ground-truth states. A simulation world specifies objects, sensors, lighting and timing. Simulation Description Format (SDF) is the structured format used for these descriptions. Rendered camera realism and accurate identity labels are separate requirements; an attractive image alone does not validate the annotations.

The ros_gz family connects ROS 2 with Gazebo. Its ros_gz_bridge component translates supported message types between the two systems. Configure bridges for images, camera information and simulation clock only as needed, and verify topic names and message mappings against the installed versions. The bridge transports data; it does not perform detection or tracking. [9, 10]

rclpy is the Python client library for ROS 2. It creates nodes, publishers, subscribers and timers from Python code. Use it for the first implementation to reduce development overhead. rclcpp is the C++ client library and is optional if profiling later identifies a critical bottleneck. A language rewrite is not an assumed requirement for real-time operation.

Quality of Service (QoS) policies control message-delivery behavior, including queue depth, reliability and durability. ROS 2 uses middleware interfaces commonly backed by Data Distribution Service (DDS), a standard for distributed data exchange. Publisher and subscriber QoS must be compatible. For high-rate camera data, bounded queues prevent growing latency; for evaluation, dropped frames must be counted even if the chosen policy permits them. Select policies by measured behavior, not by assuming reliable delivery is always lower latency. [14]

rosbag2 records and replays ROS 2 topic streams. It supports repeatable debugging and comparison, but bag playback speed, storage compression and timestamp handling must be documented. RViz2 is a ROS visualization application that can display supported images and geometric messages; a custom image overlay can additionally show boxes, identities, uncertainty and track status. Neither visualization is an evaluator. [20]

## 9. Existing software: vision and learning

OpenCV means Open Source Computer Vision Library. It provides image conversion, resizing, filtering, feature detection and motion-estimation operations. Here it supplies image preparation, a crop blur proxy and background motion estimation. The blur proxy may use the variance of image derivatives; it is only a measurable cue, not a universal measure of visibility. OpenCV does not automatically solve identity recovery simply because it contains tracking-related utilities. [16]

PyTorch is a machine-learning framework for multidimensional arrays, automatic differentiation and neural-network training. An array stored as a PyTorch tensor can run on a central processing unit (CPU) or supported GPU. Automatic differentiation computes gradients needed to fit model parameters. Use PyTorch for the detector and, only if needed, the small multilayer perceptron (MLP) recovery model. A two-layer MLP is a compact neural network, not a large generative model. [15]

YOLO stands for You Only Look Once and refers to a family of object detectors. Select one maintained implementation and a model size compatible with the measured compute budget. The Ultralytics implementation provides training, inference and tracking integration, but the exact model release is a week-one decision. Record weights, input resolution, class mapping, license and inference settings. A pre-trained checkpoint may not contain an adequate UAV class, so fine-tuning and class verification are required. [11]

Detector post-processing commonly includes non-maximum suppression (NMS), which removes overlapping lower-scoring boxes according to a rule. Keep both pre-NMS predictions and post-NMS detections for experiments that require them. Intersection over Union (IoU) is the area shared by two boxes divided by their combined area. IoU is useful for overlap-based matching, but low overlap can arise from camera motion rather than a different object.

NumPy provides efficient numerical arrays for preprocessing and analysis. SciPy provides numerical algorithms, including linear assignment routines that can solve a one-to-one matching problem after costs and unmatched options have been specified. Neither library defines the semantic correctness of a match; the project must supply the cost, gates and rejection policy. [18, 19]

scikit-learn provides conventional machine-learning estimators and calibration tools. Begin with logistic regression: a linear combination of features transformed into a probability-like score. Calibrate and validate that score before interpreting it probabilistically. Calibration is an empirical relationship between predicted confidence and observed correctness, not a guarantee for new environments. Keep the calibration data separate from the examples used to fit the scoring model. [17]

## 10. Existing software: trackers and evaluation

ByteTrack is a tracking-by-detection method: it first obtains detector boxes, then associates them with tracks. Its use of lower-confidence detections can preserve objects that would disappear under a strict detection threshold. Use a pinned implementation and retain its native baseline behavior. ByteTrack is a method name, not an acronym requiring an invented expansion. [1]

BoT-SORT is a named tracker combining motion and appearance components with camera-motion compensation. SORT in this family means Simple Online and Realtime Tracking. Appearance re-identification, often abbreviated ReID, compares visual embeddings to help recognize a previously seen object. A person-trained appearance network should not be assumed to distinguish similar UAVs. Report the appearance model, whether it is enabled and its training domain. Compare configurations transparently. [2]

TrackTrack is a contemporary baseline designed around tracks when associating detections and initializing identities. Its native method may use information removed by ordinary detector suppression. Preserve that information for a faithful native comparison. A controlled study that forces identical post-NMS boxes across all trackers is also useful, but must label any disabled TrackTrack feature explicitly. Publish both comparisons rather than misrepresenting a constrained variant as the complete method. [4, 13]

MMTracking is the OpenMMLab tracking toolbox. It offers model configurations, training/evaluation utilities and interfaces to tracking methods. It is an optional baseline environment, not a required dependency of the live ROS 2 node. The documented 0.14 installation path depends on compatible versions of MMCV, the OpenMMLab computer-vision support library, and MMDetection, its detection toolbox. Do not combine arbitrary current versions of these packages. Isolate a working environment if needed and communicate through exported detections and results. [12]

TrackEval is an evaluation toolkit for multi-object tracking. It implements established metrics including Higher Order Tracking Accuracy (HOTA), association accuracy (AssA) and identity F1 score (IDF1). Its expected file format, matching rules, class handling and ignore regions must be configured consistently. A score from mismatched labels or frame numbering is not comparable. Test the adapter on tiny sequences with known correct and incorrect identities before evaluating full runs. [8]

Each baseline record must state repository, commit identifier, dependency environment, detector inputs, parameter changes, appearance weights, camera-motion settings and runtime measurement method. Keep research-paper claims distinct from the performance reproduced locally. If an implementation cannot be reproduced within the schedule, report that limitation and preserve at least the native ByteTrack, BoT-SORT and matched recovery controls.

## 11. Supporting tools and environment policy

Python is the primary implementation language. Use virtual environments or containers so incompatible tracker dependencies do not contaminate the ROS 2 runtime. A container packages an application and its dependencies in an isolated user-space environment; it does not simulate a GPU or guarantee identical hardware timing. Docker is one possible container engine. If used, pin the image definition and accelerator runtime requirements. [24]

colcon is a workspace build tool widely used with ROS 2. It discovers packages, resolves build ordering and invokes their build systems. ament is the ROS 2 build-system family that supplies package conventions and integration. For Python nodes, use the appropriate Python packaging route and declare dependencies in package metadata. A successful build is necessary but does not prove that topics, timestamps or algorithms are correct. [23]

Git records source-code versions and changes. A commit identifier makes a specific code state referenceable. Record source commit, configuration checksum, dataset manifest identifier and model checkpoint hash for each experiment. A checksum or hash is a compact fingerprint used to detect that an artifact changed; it is not a substitute for retaining the artifact. Large datasets and model checkpoints may require separate storage referenced by the manifest. [25]

Use YAML, a human-readable structured configuration format, for parameters and launch settings. Use JSON, JavaScript Object Notation, for machine-readable run manifests and diagnostics where convenient. Use comma-separated values (CSV) for tabular event and timing exports. Fix schemas and field units rather than relying on undocumented column order. None of these formats should contain simulator truth in the inference configuration.

pytest can run Python tests for association, timestamp handling and conversions. Matplotlib can produce evaluation plots. Pandas can organize tabular experiment outputs. These are supporting tools, not components of the tracking method. Add them only where they simplify a concrete task; do not turn a minimal research prototype into an unnecessary platform.

The week-one smoke test must: create the environment; receive one simulated image with camera information; run the selected detector; update a baseline tracker; publish a valid message; record and replay a short bag; and evaluate one tiny labelled sequence. Capture exact versions only after this passes. The proposal deliberately does not invent a tested dependency lockfile.

Review licenses for code, model weights, simulation assets and external datasets before redistribution. Record attribution and any restrictions in the release manifest. This is a reproducibility requirement: a result that depends on an unavailable checkpoint or undistributable dataset needs an explicit acquisition path.

## 12. Packages to build: responsibilities

The following package names describe proposed project code. They are not existing completed packages. A package is a unit of source, configuration and declared dependencies; a node is a running program within that package. Keep algorithms callable without ROS so offline evaluation and live execution share the same implementation.

tracking_sim contains Gazebo worlds, target-path generators, camera configurations and annotation exporters. Inputs are scenario settings and random seeds; outputs are images, truth records and a manifest. It depends on Gazebo and the bridge configuration. Its acceptance check overlays projected boxes and verifies persistent simulator identities through occlusion.

tracking_interfaces defines project messages for track arrays, forecasts, lifecycle events and diagnostics. Inputs are schema decisions; outputs are generated message interfaces used by other packages. It declares units, timestamps, observer identity and observed-versus-predicted status. Its acceptance check serializes and deserializes representative messages without loss of required fields.

tracking_detector wraps the selected YOLO implementation. Inputs are images and camera metadata; outputs are mapped classes, original-image boxes, scores and optional raw predictions. Dependencies include PyTorch, the chosen detector library and image-conversion support. Its acceptance check verifies resize inversion and class mapping on known images.

tracking_core implements baseline adapters, track state, ordinary matching and the controlled recovery interface. Inputs are detections and timestamps; outputs are local tracks and candidate relationships. Dependencies include numerical and assignment libraries. Acceptance checks cover crossings, duplicate detections, missing frames and one-to-one association.

tracking_recovery contains feature extraction, training, calibration and inference for the learned score. Inputs are candidate track–detection pairs plus observable history; outputs are scores and acceptance decisions. It stores model and feature-schema versions together. Its acceptance check proves that simulator identity and truth visibility are absent from inference inputs.

tracking_prediction propagates image-plane state and covariance to fixed forecast horizons. tracking_evaluation converts results, extracts predefined recovery events and computes statistics. tracking_bringup provides ROS 2 launch configurations, namespacing, recording and diagnostic settings. Their acceptance checks respectively verify elapsed-time prediction, known-answer evaluation sequences and two-stream identity isolation.

These eight packages are an organizational proposal, not a requirement for eight separate repositories. One repository with a clear workspace layout is sufficient. If packaging overhead threatens the schedule, combine source folders while preserving the interfaces and truth/inference boundary.

## 13. Message contracts and topic design

For observer A, use a namespace such as /observer_a. The camera image and camera information arrive under that namespace. The detector publishes detections; the tracker publishes tracks; the predictor publishes forecasts. Observer B uses the same relative topic names under /observer_b. Topic names below are proposed contracts and must be finalized alongside the selected standard message definitions.

An image uses sensor_msgs/Image, a standard ROS sensor message describing timestamp, frame, dimensions, encoding and pixel data. Camera information uses sensor_msgs/CameraInfo for projection and distortion parameters. cv_bridge converts between ROS image messages and OpenCV-compatible image arrays. Confirm colour-channel order and encoding to prevent silent model-input errors. [21]

A detection array may use vision_msgs/Detection2DArray when its fields meet the contract, or a documented project wrapper when raw predictions are also needed. Preserve source image timestamp, original-image box coordinates, detector class and score. Do not use the detector score field to store recovery confidence; they describe different events.

A TrackArray message should contain source timestamp, publication timestamp where needed, observer identifier, run identifier and a list of Track records. Each Track includes local identifier, class, bounding box, normalized centre, image-plane velocity, covariance, age since last observation and lifecycle status. Suggested statuses are tentative, observed, predicted-only and terminated. Store confidence type explicitly so downstream users can distinguish detector confidence from calibrated recovery probability.

A ForecastArray message should identify its source track and reference timestamp, then provide horizon seconds, predicted normalized centre, covariance and validity status for each forecast. The same track can have forecasts at both 0.5 and 1.0 seconds. Do not publish future simulator positions or use an unstated future camera pose when forecasting.

Diagnostics should report frames received, processed, skipped and dropped; queue age; inference duration; association duration; recovery duration; total publication delay; and current memory use. Include invalid-input counters. Units must be explicit: seconds for intervals, milliseconds for latency summaries, pixels for boxes and normalized coordinates for forecast evaluation.

If a message consumer needs metric position, define a separate extension with depth source, coordinate frame and uncertainty. Never place a normalized image coordinate into a field documented as metres. Record schema version in the run manifest and preserve an adapter for any older result format used by baseline evaluation.

## 14. Runtime sequence and lifecycle rules

At each valid image timestamp, the detector returns candidate objects. The tracker predicts existing states to that timestamp using the actual elapsed interval. Ordinary active-track association executes according to the fixed baseline configuration. Only after that stage does the controlled recovery experiment examine unmatched detections and recently lost tracks.

Define track states explicitly. A tentative track has not yet accumulated enough evidence for confirmation. An observed track has a current matched detection. A lost or predicted-only track has recent history but no accepted current observation. An expired track is no longer eligible for recovery. Confirmation and expiration settings are part of the experimental configuration and must be shared by the matched heuristic and learned variants.

For each allowed lost-track/detection pair, calculate features from data available at that moment. Apply the same permissive class and geometry gates to both controlled variants. Produce a score, build an assignment cost and solve a one-to-one problem with an explicit unmatched option. Reject candidates below the chosen operating threshold. Restore the old identifier only for accepted assignments; otherwise leave the track lost and allow the ordinary new-track logic to handle the detection.

The native ByteTrack run remains a separate baseline with its own intended lifecycle. The controlled variants modify a specified recovery stage while retaining the same upstream behavior. This distinction avoids the false claim that ByteTrack lacks recovery and makes clear which comparison isolates the new model.

An illustrative sequence is: predict states; associate active tracks; construct eligible recovery pairs; compute recovery scores; assign or reject; update accepted tracks; initialize permitted new tracks; expire over-age tracks; publish states and diagnostics. In implementation, preserve native tracker ordering where required and document any change. Pseudocode is a conceptual contract, not permission to reorder a baseline silently.

Test edge cases that can invalidate identity results: two tracks competing for one detection; one track near two detections; zero detections; zero active tracks; repeated timestamps; variable frame intervals; object disappearance at a clip boundary; and a reused identifier after restart. Deterministic tie-breaking makes repeated evaluation interpretable. Log accepted recovery pairs and their scores so a false recovery can be reconstructed from saved data.

## 15. Dataset generation and partitioning

Plan approximately 320 primary single-observer clips, each 20 seconds at 20 frames per second. This is 400 frames per clip and 128,000 primary images overall. Use 160 development clips, initially allocated as 120 training and 40 validation, plus 160 held-out test clips. These are planning quantities, not a statement that the dataset already exists. Additional observer views create additional images and must be counted separately.

The test design crosses two camera-motion profiles, four occlusion durations, two blur conditions and two target groups, with five independent scenario seeds per combination: 2 × 4 × 2 × 2 × 5 = 160 clips. Occlusion durations are 0, 0.5, 1.0 and 2.0 seconds. The zero-occlusion condition is a control and usually contributes no primary occlusion-recovery events. Target groups are ground vehicles and airborne UAVs. The five seeds are independent scenario realizations within each factor combination, not a claim of five independent frames.

Define camera-motion profiles numerically in week two using angular and translational speed ranges, then freeze them in week three. A low-motion profile and a turning/accelerating profile are useful starting descriptions, but labels such as “hard” are insufficient without measured values. Similarly, define blur kernel or simulator-exposure settings explicitly. If blur is added after rendering, state that it is a controlled image degradation and not a complete sensor model.

Split whole flights before training. All frames, crops, augmented variants and camera views of a flight belong to the same partition. Hold out layouts and target trajectories where feasible. A random split of adjacent frames leaks appearance and motion history and would overstate generalization. Store partition membership in a versioned manifest and reject duplicate content across partitions.

For each clip record scenario seed, world/layout, target assets, paths, observer path, camera settings, render settings, occlusion schedule, blur setting, timestamps and annotation version. Record whether a factor was achieved as intended; a scheduled occluder does not guarantee an actual full disappearance in the image.

Generate a small pilot first. Inspect at least one example from every factor combination, estimate storage and event counts, then produce the full set. If a condition yields too few usable events, repair its scenario generator using development data before freezing the held-out test set. Do not select test clips after inspecting tracker performance.

## 16. Annotation and recovery-event protocol

Each image annotation includes persistent simulator object identity, class, projected box, visibility information and source timestamp. Clip a box to image boundaries when scoring visible image content. Record both an object’s full projected extent and its visible fraction if the simulator supports it reliably. Define minimum box size and visibility thresholds during the pilot; use the same rules for every method.

Keep hidden-object identities and projected centres for event construction and separately labelled forecast analysis. They must not enter detector training as ordinary visible boxes without an explicit task definition. The primary multi-object tracking benchmark uses eligible visible objects and observed outputs. Predicted-only outputs are evaluated separately so a tracker cannot inflate visible tracking results merely by continuing to publish uncertain hidden states.

A primary recovery event is defined from truth independently of any tracker: the target is sufficiently visible for at least one second before disappearance; it becomes unobservable while remaining inside the field of view; and it reappears after a gap no longer than two seconds. Use the same visibility threshold at onset and reappearance, with a documented persistence rule to avoid one-frame flicker events. Exclude clip-boundary events lacking the required observation windows by a predeclared rule.

Successful recovery requires the identity assigned to the correct target before the gap to be restored within 0.5 seconds after reappearance and remain correct for the following 0.5 seconds. A wrong association during this interval fails the event. If the tracker never had a correct pre-loss track, count the event as unsuccessful in the all-event primary recall; also report the subset with a correct pre-loss track as a secondary conditional analysis.

The denominator is all eligible truth events. A restrictive candidate gate, dropped frame or early track expiration does not remove an event from that denominator. This prevents methods from appearing more reliable merely by declining difficult cases. Separately count all claimed recovery actions, including false recovery actions unrelated to an eligible event, when calculating recovery precision.

Audit events by overlaying images, true identities, visibility intervals and predicted tracks. Review a random sample plus all unusual boundary cases. Keep an annotation correction log; if a test-label defect is discovered after evaluation, correct the rule consistently for all methods and disclose the rerun. Never edit only labels that harm the proposed method.

## 17. Detector training and frozen inputs

First evaluate the chosen pre-trained detector on development images. Verify that its class vocabulary includes the intended targets and that its boxes remain meaningful for very small UAVs. If the checkpoint lacks the UAV category, define the project class mapping and fine-tune using training images. Validation images guide model selection, confidence thresholds and image resolution; test images remain unseen.

Use a modest, documented training search rather than an open-ended attempt to optimize the detector. Record initialization weights, image size, augmentations, batch size, learning-rate schedule, training epochs, early stopping rule and random seeds. Batch size is the number of training examples processed together; an epoch is one pass through the training set. These settings affect both training cost and detector behavior.

Augmentations may include controlled brightness variation, scale changes and blur, but their ranges must be justified by the intended domain. Avoid transformations that create impossible geometry or alter class labels without updating boxes. Apply training augmentation only within the training partition. Keep a reproducible unaugmented evaluation path.

Measure detector precision and recall by class and object-size group. Report small-target misses and localization failures separately from association mistakes. A tracker cannot restore a currently visible target if the detector never generates a usable candidate, although a prediction may temporarily bridge missing observations. This detector ceiling is a major competing explanation for recovery failures.

After selecting the detector, freeze its weights and preprocessing for tracker comparisons. Cache raw predictions before non-maximum suppression and final detections after suppression. Include image identifiers, timestamps, confidence scores, class mapping and coordinate transforms in the cache schema. Cache files reduce repeated inference cost for algorithm experiments; they do not measure live end-to-end throughput.

Use two experimental tracks. The controlled association track supplies identical appropriate inputs to methods and explicitly labels any constrained feature. The native-system track permits each tracker’s documented input requirements while retaining the same detector weights and images where possible. Explain remaining differences. A comparison can be fair without every internal operation being identical, but those differences must be visible.

Live ROS 2 evaluation reruns detector inference and includes image conversion and message handling. Publish both cached association runtime and live pipeline runtime with clear labels. Do not describe a tracker’s speed on precomputed detections as the camera-to-track speed of the complete system.

## 18. Baselines and matched experimental controls

B0 is native ByteTrack using the frozen detector and documented threshold settings. B1 is BoT-SORT with camera-motion compensation and a stated appearance configuration. B2 is TrackTrack in a faithful supported configuration. These describe complete alternatives and provide practical context, but their differences extend beyond the proposed recovery score.

C0 is a matched hand-designed recovery control. It uses the same active-track association, candidate generation, maximum lost age, class gate, geometry gate and assignment mechanism as the proposed method. Its recovery score uses a fixed combination of normalized motion distance, box overlap and confidence, tuned on validation. Report the search space and selected weights. This control asks whether a learned score improves over a reasonable rule under the same opportunities to recover.

C1 is logistic-regression recovery using observable features. C2, only if justified by validation and time, replaces the score with a small multilayer perceptron while preserving the rest of the controlled pipeline. The primary learned method should be selected before test, not whichever model wins on the test set. Keep an uncalibrated score variant for a calibration ablation if it addresses a specific hypothesis.

Tune baselines on development data with a documented and broadly comparable effort budget. Copying one default configuration while extensively tuning the proposed model would bias the study. Do not force a person-trained appearance module onto airborne UAVs and then conclude that appearance is intrinsically unhelpful. If suitable appearance weights are unavailable, report the limitation and compare an explicitly named appearance-disabled configuration.

For TrackTrack, separate native input use from the identical-post-processing experiment. A variant deprived of suppressed detections may answer an input-controlled question but is not equivalent to the full native method. Likewise, any change to camera-motion estimation or lifecycle in another baseline must be labelled as an experimental variant.

Publish a configuration table with columns for method, detector checkpoint, raw/post-processed input, appearance model, motion compensation, active association, recovery policy, lost lifetime and tuned parameters. Keep all failure logs, including empty output and crashes. If one run fails, explain whether it is excluded for an implementation fault or scored as a system failure; apply the rule consistently.

## 19. Observable features and candidate construction

Candidate generation restricts computation before scoring. A candidate pair consists of a recently lost track and an unmatched detection of a compatible class. Use a permissive geometric gate around the predicted position, with uncertainty increasing over elapsed time. Tune that gate on validation and use it identically in matched variants. Measure how many true recoveries are excluded by the gate, because no scoring model can recover an excluded pair.

Motion innovation is the difference between a detection’s position and the track’s predicted position. Normalize it by the predicted uncertainty, for example through a Mahalanobis distance, so a given displacement is interpreted relative to expected variability. Check that the covariance is valid and numerically stable. A very small covariance can otherwise make a plausible match appear impossible.

Box geometry features include overlap, relative size change, aspect-ratio change and normalized box area. They help distinguish incompatible candidates, but abrupt perspective changes can also change a true target’s box. Use ratios with bounded or stabilized denominators and record clipping rules. Avoid absolute pixel thresholds that silently behave differently at another resolution.

History features include time since last observation, recent detection-confidence mean and variation, track age, recent displacement consistency and number of prior misses. Use elapsed seconds rather than only frame counts. When a track has insufficient history, include a missing-feature indicator and a defined fallback value; do not treat an absent measurement as a physically meaningful zero.

Image-quality features include a crop blur proxy and target size. Camera-motion features include estimated background displacement or transform parameters and fit quality, such as the fraction of background feature matches supporting the estimate. Fit quality matters because motion compensation can fail under low texture, moving foreground dominance or strong parallax. A single global transform is an approximation, especially when scene depths vary.

Mask known target regions where practical when estimating background motion. Use only current and past images. The primary model does not receive true camera pose, true target position, simulator identity or true visibility fraction. Such information may label training examples or support diagnostic upper bounds, but an oracle experiment must be clearly named and excluded from deployable-method claims.

Version the feature order, normalization statistics and missing-value rules with the checkpoint. Fit feature scaling on training data only. Log feature-distribution shifts between training, validation and test so any failure can be traced to changed conditions rather than only a final aggregate score.

## 20. Learning, calibration and threshold selection

Construct training examples from candidate pairs generated by the frozen pipeline on training flights. Label a pair positive when the detection and lost track correspond to the same true object under the annotation convention, and negative otherwise. Include difficult negatives from nearby similar objects and crossings. Do not manufacture unrealistically easy negatives that let the model succeed without learning the intended distinction.

Candidate pairs are correlated within a flight and the negative class may greatly outnumber positives. Record class prevalence and any sampling or weighting. If training uses balanced sampling, calibrate on data reflecting the natural candidate distribution or correct for the sampling scheme. Otherwise a score trained on artificial class balance can be misleading as a probability.

Start with logistic regression for interpretability, speed and a smaller tuning burden. Its output combines weighted standardized features through a logistic function. Inspect coefficient signs and stability across development seeds, but do not interpret a coefficient as a causal effect: correlated features and candidate selection can alter it.

If logistic regression systematically misses nonlinear relationships and there are enough training examples, test a compact multilayer perceptron. Predefine a small architecture search, regularization and stopping rule. Choose model capacity using development evidence. The project’s contribution does not depend on using a neural network if a simpler model performs as well.

Calibration aligns score ranges with observed match frequencies. Reserve flight-level validation subsets for calibration and operating-point selection, or use flight-grouped cross-validation if the development set is too small for separate subsets. Cross-validation repeatedly trains and validates on different development groups; it must never mix frames from the same flight across folds. Report which procedure was used and its data allocation. [17]

Select an acceptance threshold intended to achieve at least 95% recovery precision on validation while retaining as much recall as possible. Show the precision–recall trade-off and the number of supporting recovery actions. A high precision estimated from a handful of events is uncertain. Freeze the chosen threshold before test, then report achieved test precision rather than implying the target is guaranteed.

Measure calibration using the Brier score, the mean squared difference between predicted probability and the binary outcome, plus a reliability plot comparing predicted and observed frequencies. Report these over the defined candidate population and separately inspect accepted assignments. One-to-one assignment changes the selected population, so candidate-level calibration and final recovery precision answer different questions.

## 21. Assignment, rejection and uncertainty

A score for each candidate pair does not by itself produce a valid multi-object assignment. Two lost tracks may both prefer the same detection. Construct a cost matrix and solve the joint one-to-one assignment problem, with explicit dummy or unmatched options. Linear assignment can be implemented with SciPy, but rejection semantics and forbidden pairs must be encoded by the project. [18]

A possible probability-based cost is negative log of the calibrated match probability, with numerical clipping away from zero. This is a design choice to validate, not a mathematically guaranteed optimal identity decision. Specify the unmatched cost and how it relates to the selected acceptance threshold. Do not force every lost track to match merely because a solver returns a pairing.

Apply the same assignment and gating rules to the learned and matched heuristic controls. Log both the best candidate score and competing alternatives. Ambiguous cases with nearly equal scores are valuable error-analysis examples. Optional ambiguity-based rejection may be studied as an additional ablation, but it must not be added only after inspecting test failures.

Keep the maximum lost age fixed for the primary comparison. Longer memory can improve recall through long gaps while increasing the chance of attaching an old identity to a new object. An adaptive lifetime based on uncertainty is a possible secondary experiment once the fixed-lifetime result is understood. It must use the same event denominator and be labelled separately.

State uncertainty and association confidence are different. A covariance matrix describes estimated uncertainty in the motion state under the filter model. Recovery probability describes the correctness of an identity association according to empirical calibration. Neither should be substituted for the other in a message or plot. An identity can be wrong even when its estimated position is precise.

When camera-motion estimation fails, record the failure and use a documented fallback, such as skipping compensation while increasing process uncertainty. Do not insert simulator camera motion as a silent replacement. Assess whether this fallback prevents overconfident incorrect recoveries or merely increases missed recoveries.

For each false recovery in the final sample, reconstruct the preceding track, missed interval, candidate set, feature values, scores and selected assignment. Classify the mechanism: detector confusion, geometric gate exclusion, motion-model error, appearance ambiguity, calibration error or implementation defect. These analyses turn the evaluation into a research explanation rather than a leaderboard entry.

## 22. Trajectory estimation and forecasting

Use a constant-velocity Kalman filter as the primary image-plane predictor. A Kalman filter maintains a state estimate and covariance, predicts them through a motion model, and corrects them using noisy observations. Here the state is normalized horizontal position u, normalized vertical position v, and their two velocities. A box-size state may be added for tracking, but keep the forecast task defined on the target centre.

For elapsed time Δt, the predicted horizontal position is the current u plus horizontal velocity multiplied by Δt; vertical position is propagated similarly. Process noise accounts for unmodelled acceleration and camera motion. Measurement noise accounts for uncertain box localization. Tune these noise settings on development flights and use identical predictor settings for controlled recovery variants unless the experiment explicitly studies the predictor.

Forecast centres at 0.5 and 1.0 seconds after each eligible reference time. For average displacement error, evaluate a documented set of intermediate times within the horizon, matching truth timestamps by interpolation when necessary. A forecast must use only information available at its reference time. Recomputing the forecast after observing future frames would leak the answer.

Average Displacement Error (ADE) is the mean Euclidean distance between predicted and true positions across the chosen future time points. Final Displacement Error (FDE) is the distance at the horizon endpoint. Report normalized image-coordinate error, and optionally convert it to pixels at a declared resolution for intuition. These values are not metre-level trajectory errors.

Identity consistency is part of forecasting validity. A low position error attached to the wrong target is not a successful forecast. Report forecast availability, the proportion with correct identity, errors conditional on valid identity, and a separate count of identity failures. Do not improve apparent prediction accuracy by silently dropping hard forecasts from the denominator.

Propagate state covariance and draw a nominal 95% ellipse for position uncertainty. Under the ideal two-dimensional Gaussian model, the ellipse is defined by a squared Mahalanobis-distance threshold of about 5.991. Real residuals may violate that model, so measure the fraction of truth points inside the ellipse and the ellipse area. Very large ellipses can achieve coverage while being uninformative.

A monocular moving camera mixes observer and target motion. The core predictor therefore estimates image motion, not a physical flight path. A later metric extension requires calibrated depth or ranging and observer pose, separate uncertainty propagation, and a new evaluation protocol in physical units.

## 23. Metrics and statistical analysis

Recovery recall equals successful eligible recovery events divided by all eligible truth events. Recovery precision equals correct claimed recovery actions divided by all claimed recovery actions. Define how repeated recovery attempts for the same event are counted before evaluation; preserve an action-level log and an event-level table. Report raw counts alongside ratios so a percentage from very few examples is visible.

HOTA, Higher Order Tracking Accuracy, jointly evaluates detection and association behavior over matching thresholds. AssA isolates its association-accuracy component. IDF1 is an identity-based F1 score balancing identity precision and recall. Identity switches and fragmentation counts expose failure types that may be hidden in an aggregate metric. Use TrackEval’s documented implementation and report the exact configuration rather than writing an unverified approximation. [8]

Break results down by camera-motion profile, occlusion duration, blur condition, target group and object size. The full factorial test design supports structured comparisons, but five scenario seeds per condition may still yield wide intervals. Report uncertainty and avoid presenting every small difference as meaningful. Zero-occlusion controls help identify general identity damage even though they contribute few or no recovery events.

Pair methods on the same flights. Estimate confidence intervals by resampling whole flights or scenario clusters, not individual adjacent frames. A bootstrap repeatedly samples these independent units with replacement and recomputes the paired difference. Use a predeclared number of replicates, for example 2,000, and document the seed. Preserve all views of a flight in the same resampling unit.

For HOTA and related sequence metrics, recompute the appropriate aggregate within each resampled set when feasible; do not assume a simple average of per-frame or per-clip scores matches the official aggregate. For recovery ratios, resample event counts through their parent flights. Report both overall results and whether effects are concentrated in a small number of scenes.

The primary inference concerns H1. Treat the many subgroup and ablation comparisons as secondary or exploratory unless a limited confirmatory set and multiplicity procedure are specified before testing. Provide effect sizes and confidence intervals, not only significance labels. If intervals are broad, the conclusion is limited precision, not proof of equivalence.

Repeat training with several development seeds if resources permit and distinguish model-training variability from scenario variability. Select one predeclared reporting rule for the final trained model or report all selected-seed runs. Do not choose the best test seed. Preserve failed runs and explain any exclusions in the final report.

## 24. Experiment matrix and runtime protocol

E1 establishes native baseline performance for ByteTrack, BoT-SORT and TrackTrack. E2 compares the matched heuristic recovery rule against the learned score with identical candidate opportunity and active association. E3 removes feature groups: confidence/history, camera-motion/fit quality, and image-quality/size cues. E4 assesses calibration and threshold trade-offs. E5 evaluates forecasts and uncertainty. E6 measures live single- and two-observer performance.

Prioritize E1 and E2. If time is constrained, reduce optional model variants and secondary feature combinations before dropping the matched control or held-out evaluation. A useful ablation removes one causal explanation at a time; a large grid of poorly motivated settings consumes time without necessarily clarifying the result.

For live timing, record image-arrival wall-clock time, detector start/end, association start/end, recovery start/end and publication time. The primary latency is image availability to published tracking output on the same machine. If claiming sensor-capture-to-output latency across machines, clock synchronization and transport delay must also be measured. The plan does not assume those clocks are already synchronized.

Report median, 95th percentile and maximum observed latency, sustained processed frames per second, input frame rate, dropped-frame fraction, queue age and memory usage. State whether model warm-up is excluded and show startup behavior separately. Fix image resolution, detector weights, precision mode and hardware. Measure for a sustained interval long enough to reveal queue buildup or thermal effects, with duration finalized during the pilot.

In simulation, report real-time factor and wall-clock throughput together. A nominal 20-frame-per-second simulated camera may produce fewer images per wall-clock second when rendering is slow. Test cached detector-free association separately from full live inference. Report whether simulator rendering shares the GPU with the detector, because contention can dominate latency.

For two observers, maintain independent state and identifiers, then measure aggregate throughput and per-stream tail latency. A total of 40 processed frames per second can conceal starvation of one stream, so report each stream separately. Test simultaneous starts, one stalled stream and restart isolation.

The goal is an honest operating envelope: the combinations of resolution, target count and stream count meeting the proposed latency and accuracy criteria. If the initial detector is too slow, reduce model size or image resolution through validation and rerun relevant accuracy comparisons. Do not optimize runtime after test without documenting the resulting new configuration.

## 25. Weeks 1–6: establish the experiment

Week 1 — scope and research audit. Review the closest papers and public implementations, complete the related-work matrix, decide whether the narrow algorithmic claim is defensible, and perform the environment smoke test. Deliver a scope statement, version inventory and initial claim map. Exit gate: one image can pass through detection, tracking, publication and basic evaluation.

Week 2 — simulation and truth. Build a minimal world with one observer and scripted targets; then add occluders, crossings and two camera-motion profiles. Implement timestamp-aligned labels and a visual annotation audit. Deliver a small pilot dataset and generator configuration. Exit gate: boxes, identities and visibility labels are correct on manually checked cases.

Week 3 — dataset and protocol freeze. Finalize class mapping, minimum-size and visibility rules, recovery-event definition, split logic and test factor settings. Estimate storage and generate development data plus a sealed test manifest. Deliver the dataset specification and evaluation protocol. Exit gate: no flight or augmented copy crosses partitions; the planned conditions produce usable events.

Week 4 — detector selection. Evaluate the starting checkpoint, fine-tune if required, and choose resolution and thresholds using development data. Export raw and post-processed detection caches. Deliver a detector report with class/size breakdowns and frozen checkpoint. Exit gate: target classes are meaningful and the detection ceiling is understood.

Week 5 — reproducible baselines. Run native ByteTrack and BoT-SORT, establish TrackTrack where feasible, and implement the matched heuristic recovery control. Verify evaluation adapters on tiny known-answer sequences. Deliver baseline configurations and a first development-results table. Exit gate: identical inputs and lifecycle differences are documented; baseline tuning is adequate.

Week 6 — learned recovery. Extract training candidate pairs, fit logistic regression, inspect hard negatives and calibrate scores. Test a small neural model only if a clear limitation of the linear score justifies it. Deliver feature schema, training script and validation precision–recall results. Exit gate: inference uses only observable features and the chosen operating point is defensible.

Reserve time each week for integration and writing. The schedule assumes existing assets and a modest detector fine-tuning task; it is not a guarantee that every software stack will install without effort. Record time spent and unresolved risks at the weekly review. If a gate fails, simplify optional scope immediately instead of allowing the final evaluation period to disappear.

## 26. Weeks 7–12: integrate and establish evidence

Week 7 — live integration. Connect recovery to the ROS 2 tracker, publish lifecycle status and diagnostics, and test timestamp/drop behavior. Deliver a reproducible launch configuration and recorded demonstration. Exit gate: online and offline code agree on the same replayed detections within stated numerical tolerances.

Week 8 — forecasts and consumers. Add 0.5 and 1.0 second image-plane forecasts, covariance outputs and visualization. Validate elapsed-time updates and coordinate conversions. Deliver forecast messages and evaluation scripts. Exit gate: predictions use no future data and predicted-only states are visibly distinguished from observations.

Week 9 — ablations and freeze. Complete development feature ablations, threshold selection and runtime tuning. Freeze the primary model, baseline configurations, metric implementation, hypothesis wording and reporting rules. Deliver an experiment manifest and preregistration-style protocol note. Exit gate: the held-out test can be run without further methodological decisions.

Week 10 — held-out experiments. Run the frozen methods across test clips and measure live one- and two-observer performance. Deliver raw per-flight outputs, recovery-action logs and timing traces. Exit gate: every planned condition has complete outputs or an explicitly recorded failure; test results have not been used to retune the reported configuration.

Week 11 — interpretation and transfer check. Calculate paired confidence intervals, inspect false recoveries and characterize detector versus association limitations. If suitable licensed real video exists, conduct a clearly labelled transfer sanity check without claiming that it establishes operational flight safety. Deliver figures, representative cases and limitations. Exit gate: claims are supported by both aggregate results and failure analysis.

Week 12 — report and release. Produce the research report, reproducibility instructions, dataset manifests, model documentation and the presentation. Run the documented setup from a clean environment where practical. Deliver a tagged code state, configurations, evaluation outputs and demonstration recording. Exit gate: another researcher can identify and rerun the exact reported experiment.

Weekly research-group checkpoints should focus on decisions: validity of labels, sufficiency of baselines, novelty overlap, operating-point choice and interpretation of uncertainty. The final group presentation should ask for feedback on the contribution and next experiment, not imply that prospective targets have already been achieved.

The critical path is environment → trustworthy labels → frozen detector → credible baselines → learned recovery → frozen evaluation. Forecasting sophistication, real-video transfer and metric-depth extensions are secondary. If schedule pressure occurs, preserve the critical path and a complete, honest research result.

## 27. Resources, storage and ownership

The resource assumption is one researcher with access to a workstation containing a compatible GPU with approximately 8–16 gigabytes of video random-access memory (VRAM), 32 gigabytes of system random-access memory (RAM), and sufficient storage. VRAM holds GPU model parameters and intermediate tensors; RAM supports the operating system, simulation and analysis. These are planning estimates, not measured requirements or a recommendation to purchase a specific device.

Storage must be measured from the pilot. At 1,280 × 720 pixels with three 8-bit colour channels, one uncompressed image occupies 2,764,800 bytes. The planned 128,000 primary images therefore occupy about 354 gigabytes in decimal units, or about 330 gibibytes in binary units, before metadata, duplicate bags, detector caches and checkpoints. Additional camera views increase this total. The common 100–200 gigabyte estimate is plausible only for a measured compressed workflow, not for all raw images.

Provision roughly half a terabyte or more if retaining the complete uncompressed primary set and working copies; determine the actual margin from measured assets and compression. Avoid storing the same pixels in several forms without purpose. A sensible layout retains a canonical dataset, manifests, compact detection caches and selected replay bags. Record compression settings because lossy compression can alter small targets and blur cues.

Compute time depends on the detector, image size, simulator rendering and number of training runs. Use the pilot to estimate hours for generation, training and evaluation rather than inventing a fixed cloud cost. Log GPU use and wall-clock time. If resources are shared, schedule long generation or training jobs and reserve a quiet interval for runtime measurement.

The researcher owns implementation, manifests and experiment execution. A supervisor or designated reviewer should review the novelty matrix, annotation samples, frozen protocol and final claims. These are suggested roles; no individuals have been assigned. A second reviewer checking a sample of failure cases reduces the risk of interpreting ambiguous events in favour of the proposed method.

Maintain one issue log with severity, owner, next action and effect on the main claim. Keep source and configurations under version control; keep datasets and checkpoints with durable identifiers and integrity hashes. Backup irreplaceable labels and results. Temporary renders and reproducible caches can be regenerated, but final manifests and raw measurements are part of the research evidence.

## 28. Risks, fallbacks and scope protection

Risk: a recent paper already implements the proposed recovery score. Mitigation: audit methods and code before claiming novelty. Fallback: frame the contribution as a controlled aerial recovery benchmark and reproducible comparison, or select a narrower justified variation. Do not enlarge the project into an entirely new tracking architecture merely to preserve a novelty claim.

Risk: small UAVs are rarely detected. Mitigation: inspect detector recall by size and class, refine training data and choose resolution through validation. Fallback: state the detection-limited operating range and evaluate association where sufficient candidates exist, while retaining all-event results. Do not remove difficult targets from the test set after seeing performance.

Risk: camera-motion estimation is unreliable. Mitigation: measure fit quality, mask foreground objects where practical and expose failure flags. Fallback: skip compensation and increase motion uncertainty according to a documented rule. Compare this behavior explicitly; simulator pose may be used only in a labelled oracle diagnostic.

Risk: synthetic artifacts dominate learning. Mitigation: hold out layouts, trajectories and seeds; vary assets and rendering within scope; inspect feature shifts. Fallback: narrow conclusions to the tested simulation distribution and propose a real-data follow-up. A small qualitative demonstration is not a substitute for representative evaluation.

Risk: software dependencies conflict. Mitigation: perform the week-one smoke test, pin working versions and isolate MMTracking or other legacy stacks. Fallback: use common exported detections to evaluate the separate environment. Do not spend the entire project repairing a secondary baseline while leaving the main experiment incomplete.

Risk: recovery improves recall but creates wrong identities. Mitigation: prioritize precision, show the full trade-off, preserve an unmatched option and analyze false recovery actions. Fallback: publish the limitation or adopt a more conservative operating point selected on validation. The result may demonstrate that the learned score is not useful under the tested conditions.

Risk: two-stream timing misses the target. Mitigation: profile per-stage latency and report per-stream performance. Fallback: retain a complete single-stream result and describe the measured scaling limitation. Avoid claiming onboard readiness from a desktop result.

Risk: too many optional ideas dilute the study. Protect the primary deliverable: frozen detector, credible baselines, matched control, learned score, sealed test and reproducible analysis. Shared cross-camera identities, learned long-horizon forecasting, real flight control, weather simulation and depth-based separation remain extensions unless the core work finishes early.

## 29. Deliverables, acceptance and future work

D1 — a runnable research workspace. Deliver source, dependency versions, launch configurations, checkpoint identifiers and a short installation guide. Acceptance means the documented smoke test produces detections, tracks and forecasts from a known replay. Include the exact hardware and software context of reported runtime results.

D2 — a dataset and protocol package. Deliver scenario generators, split manifests, label schemas, visibility rules, recovery-event rules and a licensing/availability statement. Acceptance means an independent reader can reconstruct why each event was eligible and verify that no test flight was used for training or calibration.

D3 — a comparison package. Deliver native baseline settings, matched control settings, model training/calibration code, frozen thresholds, per-flight outputs and timing traces. Acceptance means every reported table or plot can be regenerated from retained outputs. Include negative and failed runs according to the declared reporting rule.

D4 — a scientific report. Structure it around motivation, related work, precise intervention, experimental protocol, results, ablations, failure analysis and limitations. State which novelty claims survived the audit. Distinguish a statistically uncertain difference from evidence of no practical improvement. Avoid using “real-time” without hardware, resolution, stream count, latency and throughput evidence.

D5 — a demonstration and research-group presentation. Show camera-local identities, observed/predicted-only status and short forecasts under crossings and occlusion. The ten-slide proposal deck accompanying this plan presents prospective work; replace targets with measured results only after experiments are complete. Speaker notes carry definitions, methodological caveats and source links.

The next research step depends on the evidence. If recovery helps reliably, test a more diverse real dataset and embedded hardware. If camera motion dominates, investigate better motion estimation while preserving matched controls. If ambiguity dominates, evaluate suitable appearance features or additional sensors. If prediction remains poorly calibrated, improve uncertainty modelling before using forecasts for downstream decisions.

A metric separation extension would add stereo, depth or ranging, calibrated camera/observer pose and uncertainty propagation into a common physical frame. A cooperative multi-drone extension would add time synchronization, communication constraints and cross-camera identity association. A collision-avoidance extension would additionally require a decision policy and a separate validation argument. These are distinct projects built on the perception evidence, not outcomes already established by this proposal.

Completion is defined by a reproducible answer to the primary research question, not by achieving every prospective numerical target. The final contribution should be the strongest claim the evidence supports, including an informative negative result.

## 30. Glossary: research and tracking

AI — artificial intelligence: computational methods that perform tasks such as recognizing objects or learning association rules from examples.

UAV — unmanned aerial vehicle: an aircraft operated without a human pilot onboard. “Drone” is used informally for these aerial platforms in this project.

MOT — multi-object tracking: estimating the identities and states of multiple objects over a sequence. The full phrase is preferred in the plan.

YOLO — You Only Look Once: a family of object detectors. A specific implementation, model and checkpoint must be named in experiments.

SORT — Simple Online and Realtime Tracking: a tracking-method name that appears within the BoT-SORT family. ByteTrack, TrackTrack, DroneMOT, DMTrack, DynUAV and JitTrack are method or project names; this plan does not invent expansions for them.

IoU — Intersection over Union: intersection area divided by union area for two shapes, usually bounding boxes here. NMS — non-maximum suppression: a rule for suppressing overlapping detector outputs. ReID — re-identification: matching visual appearance across observations.

MLP — multilayer perceptron: a feed-forward neural network with learned layers. Calibration — empirical agreement between a predicted probability and observed frequency. Brier score — average squared probability error for a binary event.

HOTA — Higher Order Tracking Accuracy: a metric combining detection and association behavior. AssA — association accuracy, a component used in HOTA evaluation. IDF1 — identity F1 score, balancing identity precision and identity recall. F1 is a harmonic-mean score, not an acronym for a software package.

ADE — Average Displacement Error: mean forecast-position error across specified future times. FDE — Final Displacement Error: forecast-position error at the horizon endpoint. CI — confidence interval: an interval produced by a statistical procedure to express estimation uncertainty; the document generally writes the phrase in full.

Occlusion — loss of visibility behind another surface. Association — linking a detection to a track. Recovery — restoring the correct prior identity after an interruption. Ground truth — reference labels used for training or evaluation, not a permitted hidden runtime sensor. Ablation — a controlled experiment that removes or replaces one component to investigate its contribution.

2D and 3D — two-dimensional and three-dimensional. The core task uses 2D image coordinates. Metric 3D state requires additional geometric information. Hz — hertz, events per second; FPS means frames per second. Millisecond — one thousandth of a second.

## 31. Glossary: systems and implementation

ROS 2 — Robot Operating System 2, robotics middleware and tools. QoS — Quality of Service, policies governing message delivery. DDS — Data Distribution Service, a distributed-data communication standard used by common ROS 2 middleware implementations. SDF — Simulation Description Format, a format for virtual worlds, models and sensors.

CPU — central processing unit. GPU — graphics processing unit, used here for parallel model computations and potentially rendering. RAM — random-access memory, the machine’s working memory. VRAM — video random-access memory associated with the GPU. A byte is eight bits; GB denotes a decimal gigabyte and GiB denotes a binary gibibyte.

API — application programming interface: documented functions and data contracts through which programs interact. YAML — a human-readable configuration serialization format, historically named “YAML Ain’t Markup Language.” JSON — JavaScript Object Notation, a structured data format. CSV — comma-separated values, a tabular text format. XML — Extensible Markup Language, used by several robotics configuration formats; readers need not edit it directly to understand the research.

OpenCV — Open Source Computer Vision Library. MMTracking — the OpenMMLab tracking toolbox. MMCV — OpenMMLab’s computer-vision support library. MMDetection — OpenMMLab’s detection toolbox. NumPy, SciPy, PyTorch and scikit-learn are library names; their practical roles are explained in sections 9–11.

rclpy — the ROS 2 Python client library; rclcpp — the ROS 2 C++ client library. sensor_msgs and vision_msgs are ROS message-package names. cv_bridge converts image representations. tf2 manages coordinate transforms. ros_gz_bridge translates supported messages between Gazebo and ROS 2. rosbag2 records and replays topic data. RViz2 visualizes supported ROS data.

colcon — a multi-package build tool. ament — a ROS 2 build-system family. Git — a version-control system. Docker — a container tool. pytest — a Python testing framework. Matplotlib — a plotting library. Pandas — a tabular-data analysis library. “Package” can mean a reusable installed dependency or a unit of project code; the tracking_* packages in section 12 are proposed project code.

ECCV — European Conference on Computer Vision. CVPR — Conference on Computer Vision and Pattern Recognition. ICRA — International Conference on Robotics and Automation. IJCV — International Journal of Computer Vision. A preprint is a publicly shared manuscript whose peer-review status must be checked rather than assumed. arXiv is a preprint repository, not itself a peer-review venue.

## 32. References: research and core tools

Primary papers and official documentation. Literature and documentation checked through 16 October 2026. Versions selected for the implementation must still pass the installation and reproduction gates.

[1] Zhang et al. ByteTrack: Multi-Object Tracking by Associating Every Detection Box. ECCV 2022. [Source](https://arxiv.org/abs/2110.06864)

[2] Aharon, Orfaig and Bobrovsky. BoT-SORT: Robust Associations Multi-Pedestrian Tracking. 2022. [Source](https://arxiv.org/abs/2206.14651)

[3] Wang, Wang and Li. DroneMOT. ICRA 2024 / author manuscript. [Source](https://arxiv.org/abs/2407.09051)

[4] Shim et al. Focusing on Tracks for Online Multi-Object Tracking (TrackTrack). CVPR 2025. [Source](https://openaccess.thecvf.com/content/CVPR2025/html/Shim_Focusing_on_Tracks_for_Online_Multi-Object_Tracking_CVPR_2025_paper.html)

[5] Fu et al. DMTrack. 2025 preprint. [Source](https://arxiv.org/abs/2510.17860)

[6] Ye et al. DynUAV. 2026 research paper / author manuscript. [Source](https://arxiv.org/abs/2603.05970)

[7] Shan and Zhang. JitTrack. August 2026 preprint. [Source](https://arxiv.org/abs/2608.10485)

[8] Luiten et al. HOTA: A Higher Order Metric for Evaluating Multi-Object Tracking. IJCV 2021. Implementation: github.com/JonathonLuiten/TrackEval. [Source](https://arxiv.org/abs/2009.07736)

[9] Gazebo documentation. Installing Gazebo with ROS; supported release pairings. [Source](https://gazebosim.org/docs/harmonic/ros_installation/)

[10] Gazebo documentation. ROS 2 integration and message bridging. [Source](https://gazebosim.org/docs/harmonic/ros2_integration/)

[11] Ultralytics documentation. Multi-object tracking and supported tracker configuration. [Source](https://docs.ultralytics.com/modes/track/)

[12] MMTracking documentation. Installation and dependency compatibility. [Source](https://mmtracking.readthedocs.io/en/latest/install.html)

[13] Ultralytics documentation. TrackTrack implementation reference; compare with the authors’ repository at github.com/kamkyu94/TrackTrack. [Source](https://docs.ultralytics.com/reference/trackers/track_tracker)

## 33. References: supporting documentation

Primary papers and official documentation. Literature and documentation checked through 16 October 2026. Versions selected for the implementation must still pass the installation and reproduction gates.

[14] ROS 2 Jazzy documentation. Quality of Service settings. [Source](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html)

[15] PyTorch documentation. Quickstart tutorial and core model workflow. [Source](https://docs.pytorch.org/tutorials/beginner/basics/quickstart_tutorial.html)

[16] OpenCV documentation. Library introduction. [Source](https://docs.opencv.org/4.x/d1/dfb/intro.html)

[17] scikit-learn documentation. Probability calibration. [Source](https://scikit-learn.org/stable/modules/calibration.html)

[18] SciPy documentation. Linear sum assignment. [Source](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html)

[19] NumPy documentation. What is NumPy? [Source](https://numpy.org/doc/stable/user/whatisnumpy.html)

[20] ROS 2 rosbag2 repository and documentation. [Source](https://github.com/ros2/rosbag2)

[21] ROS perception vision_opencv repository, including cv_bridge. [Source](https://github.com/ros-perception/vision_opencv)

[22] ROS 2 geometry2 repository, including tf2. [Source](https://github.com/ros2/geometry2)

[23] colcon documentation. [Source](https://colcon.readthedocs.io/en/released/)

[24] Docker documentation. Container and Docker overview. [Source](https://docs.docker.com/get-started/docker-overview/)

[25] Git documentation. Version-control introduction. [Source](https://git-scm.com/book/en/v2/Getting-Started-About-Version-Control)

Research proposal • 16 October 2026
