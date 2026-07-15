# Annotation Guidelines and Scoring Rules

## Annotation Units

A TAP consists of three string fields:

- `trigger`: the event, state change, numeric threshold, or time point that initiates the rule.
- `condition`: guards that must hold when the trigger fires.
- `action`: one or more assignments or `call_action:` commands to execute.

Atoms use the existing benchmark syntax:

- State/property atom: `device.service.property<op>value`
- Event trigger: `event:device.service.event`
- Service action: `call_action:device.service.action`
- Time atom: `time>=HH:MM`, `time<=HH:MM`, or `time==HH:MM`

Multiple action atoms are comma-separated. Multiple condition atoms are joined with `and` unless an acceptable variant explicitly states otherwise.

## Category Definitions

- `Basic TAP`: one explicit trigger and one explicit action, no condition.
- `Conditional TAP`: one explicit trigger, at least one explicit condition, and one explicit action.
- `Multi-Action TAP`: one explicit trigger and multiple explicit actions; explicit conditions may be present.
- `Constraint-Aware TAP`: the request requires an executable TAP that includes operational dependencies or environmental interlocks not stated in the user request.

## Explicit Intent Labels

Annotate `explicit_tap` using only information stated in the user request.

Include:

- Named trigger device and event/state/threshold.
- Named condition device, threshold, time range, or state if mentioned.
- Named action device, property/action, and target value if mentioned.
- Multiple requested actions if the user lists them.

Exclude:

- Power-on dependencies needed before setting brightness, color temperature, fan level, target humidity, mode, or target temperature unless the user explicitly says to turn the device on.
- Environmental interlocks such as closed windows/doors unless the user explicitly mentions them.
- KG-specific helper atoms that make the automation deployable but are not part of the natural-language intent.

## Implicit Constraint Labels

Annotate only constraints needed for executable behavior or safe/environmentally appropriate operation.

### Dependencies

Use `implicit_constraints.dependencies` for action atoms that must be executed before or together with the explicit action:

- Setting light brightness or color temperature requires `light.on=true` when the request only says to set brightness/color temperature.
- Setting air-conditioner mode or target temperature requires `air_conditioner.on=true` unless the request explicitly says to turn/switch it on.
- Setting humidifier target humidity requires `humidifier.on=true` unless explicitly requested.
- Setting a range hood fan level requires `hood.on=true` unless explicitly requested.

### Interlocks

Use `implicit_constraints.interlocks` for condition atoms that prevent unsafe or undesirable execution:

- Running an air conditioner requires the relevant window sensor to indicate closed when this is part of the home knowledge but not stated in the request.
- Running bathroom heater heat mode requires the bathroom door to be closed when this is part of the home knowledge but not stated in the request.

## Acceptable Variants

Use `acceptable_taps` for full executable TAPs that are semantically equivalent. Examples include:

- Event trigger versus equivalent state trigger when both represent the same physical event.
- Equivalent service aliases, such as different MiOT services that expose the same TV turn-off action.

Do not use acceptable variants to hide missing dependencies or interlocks; those should be represented through explicit and implicit labels.

## Automatic Scoring

### Explicit-Intent Score

The generated TAP receives `explicit_intent.score = 1` if every atom in `explicit_tap` is present in the generated TAP in the same role. Additional implicit atoms are allowed and do not reduce this score. The evaluator also records precision, recall, missing atoms, and extra atoms for analysis.

### Implicit-Constraint Completion

The generated TAP is checked against `implicit_constraints`:

- Dependency atoms must appear in the generated `action` field.
- Interlock atoms must appear in the generated `condition` field.

The primary value is `implicit_constraints.completion`, the recall over all annotated implicit atoms. The binary `implicit_constraints.score` is 1 only when all applicable implicit atoms are present. This score is reported for applicable rows and is primarily aggregated over `Constraint-Aware TAP`.

### Executable Correctness

`executable_correctness` is the original exact-match metric over the full `tap` target. Trigger, condition, and action atom sets must each match an accepted executable TAP candidate.

### Platform Validity

`platform_validity.score = 1` when the generated TAP is a dictionary with string `trigger`, `condition`, and `action` fields; every non-time atom references a real device and capability in the target home; each atom uses a capability whose `TAP_role` permits that field; and the TAP is successfully deployed to Home Assistant. Hallucinated devices/capabilities, illegal role usage, or deploy failures are scored as 0.

### Grounding Precision and Recall

Device-level and capability-level precision/recall are computed from the system's retrieved or selected context against the benchmark ground truth. If the system attempts a request but fails before producing a grounding result, the corresponding device/capability precision and recall are scored as 0 rather than being omitted from the aggregate.

## Reporting

Report two orthogonal breakdowns:

- By request category: `Basic TAP`, `Conditional TAP`, `Multi-Action TAP`, `Constraint-Aware TAP`.
- By scoring target: explicit-intent score, implicit-constraint completion, executable correctness, platform validity, and grounding precision/recall when applicable.

For non-constraint-aware rows with no annotated implicit atoms, implicit-constraint completion should be treated as not applicable rather than as a perfect score in the main aggregate.
