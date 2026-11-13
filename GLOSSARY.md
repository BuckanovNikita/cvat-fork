# Team Analytics

The language for measuring how annotation work is done in this CVAT fork: who worked, for how long, on what, and by which means. It exists so that figures on the Team Analytics page mean the same thing to maintainers, to the people who build it and to the people who read it.

## Language

### Who and where

**Team Analytics**:
The page that shows work figures for a team, per annotator, per project and overall.
_Avoid_: Analytics, dashboard, statistics page

**Grafana**:
The stock event dashboards, opened from the header link of the same name. That link was formerly labelled "Analytics".
_Avoid_: Analytics

**Annotator**:
Any person who did job work in the period, whatever their role or the stage of the job. A reviewer is an annotator here; a technical account is not.
_Avoid_: User, member, reviewer, worker

**Technical account**:
A user account that stands for an automated process rather than a person. It is never listed among people, and every box it saves counts as a Model box.
_Avoid_: Service user, bot, script user

**Job work**:
Activity performed inside an opened job. Only job work is measured; browsing lists, settings and other pages is not.
_Avoid_: Activity, usage

**Organization scope**:
The figures of one organization, seen by its owners and maintainers and by administrators who selected it.

**Instance scope**:
The figures of every organization and of personal workspaces together, seen only by an administrator with no organization selected.
_Avoid_: Global, all organizations

**No project**:
The bucket for job work in tasks that belong to no project.

### Time

**Session**:
One uninterrupted interval of job work by one person. A pause longer than the session gap ends it. Seen for a single project, a session counts if it touched that project, and its length is only the time spent inside it.
_Avoid_: Visit, login, shift

**Session gap**:
The longest pause that still belongs to the same session: five minutes.

**Working time**:
The time the server counts as worked, the same figure Grafana reports. It is the only total: every breakdown of time adds up to it.
_Avoid_: Active time, time spent, effort, hours

**Time per operation**:
The time from a person's previous action to the end of the operation, so that finding, deciding and pointing are part of it.
_Avoid_: Duration, action time

**Idle pause**:
A pause longer than 100 seconds before an action. It belongs to no operation.

### Objects and operations

**Bounding box**:
A rectangle drawn on a single frame. A rectangle that follows an object across frames is a track, not a bounding box.
_Avoid_: Bbox (in user-facing text), rectangle, box track

**All shapes**:
Every kind of object together, bounding boxes included. Figures recorded before shape tagging exist only in this form.

**Operation**:
One of the four things a person does to an object: Creation, Alignment, Class change or Deletion. Operations count what people did, not what survives: an undone creation is still a creation.
_Avoid_: Action (an action is any single recorded step), edit

**Creation**:
A person making a new object by drawing, pasting or propagating it. Model boxes are not creations.

**Alignment**:
Bringing one existing object into place: an uninterrupted run of drags and resizes of the same object, however many it takes. Touching another object or leaving the frame ends it, so returning to the same object later is a new alignment.
_Avoid_: Adjustment, correction, edit, resize

**Class change**:
Giving an existing object a different label.
_Avoid_: Relabel, label change

**Deletion**:
Removing an object.

**Other**:
Working time that belongs to none of the four operations: navigation, review, other tools and quiet moments.

**Creation method**:
How a box came to exist: Drawn, Pasted, Propagated or Model.

**Drawn**:
Created by hand from scratch.

**Pasted**:
Created as a copy through copy and paste.

**Propagated**:
Created as a copy of an object onto other frames.

**Model**:
Created without a person drawing it: saved by a technical account or produced by the built-in detector. Model boxes have counts but no time.
_Avoid_: Auto, automatic annotation, pre-annotation

**Saved boxes**:
Boxes the server stored when a job was saved, whatever their creation method. The only box figure that exists for a legacy period.

### Keyboard and mouse

**Hotkey action**:
One use of a keyboard shortcut, named by what it does rather than by the key, so a remapped key is still the same action. A held key is one action, except for frame navigation, where every frame moved is one.
_Avoid_: Key press, shortcut press, keystroke

**Mouse action**:
One click on a button, menu or sidebar control. Clicks on the canvas are drawing and editing, not mouse actions.
_Avoid_: Click

**Hotkey share**:
Hotkey actions as a part of hotkey and mouse actions together.

### Reading the page

**Period**:
The span of time the figures cover: Week (the last 7 days), Two weeks (the last 14 days), Month (one calendar month, the current one to date) or Year (the last 12 months).
_Avoid_: Date range, interval

**Trend**:
How a figure changed over the last twelve weeks or months, independent of the selected period.

**Comparison**:
Up to five annotators or projects drawn together in a trend.

**Overview**:
The page with all charts at once, each showing only its top rows.

**Full view**:
One chart alone on the page with every row, opened from the overview and closed back to it.
_Avoid_: Modal, popup, details, expanded view

**Processed history**:
The part of the past for which figures have been computed. A period is offered only when all of it is processed.

**Legacy period**:
A period recorded before shape tagging, class changes and hotkey use were logged. It has sessions, working time, projects, all-shape operations and saved boxes, and nothing else.
_Avoid_: Old data, pre-deployment period
