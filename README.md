FPS3010 Python Interface
========================

Two incomplete interfaces:
* TCP interface, using the telegram protocol ([fpsensor/proto])
* ctypes bindings for the supplied userlib ([fpsensor/userlib])

Both were restructured and put into this package and, post-restructuring,
untested.


TCP Interface
=============

Issues:

* Can't access through USB while TCP is polling
* Firmware (?) instability requires restarting FPSensors at a certain point


Userlib Interface
=================

Issues:

* Can't use Daisy at the same time
* 
