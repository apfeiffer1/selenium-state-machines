.. State Machines for Selenium documentation master file, created by
   sphinx-quickstart on Fri Jun 19 19:10:41 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

State Machines for Selenium - Documentation
=======================================================

A small library for building state machines to describe interactions with web applications and assertions over their results, all currently using Selenium.

.. autoclass:: state_machine_testing.StateMachine
   :members: __init__, write_to_file, run, add_state, add_transition

.. autoclass:: state_machine_testing.StateSequence
   :members: driver, store

.. autoclass:: state_machine_testing.StateMachineState
   :members: add_outgoing_transition

.. autoclass:: state_machine_testing.StateMachineTransition
   :members: set_target_state
