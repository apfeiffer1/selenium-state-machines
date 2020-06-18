# State Machines for Selenium

This is a small library that allows you run Selenium tests as state machines.

The general idea is that states are sets of assertions and transitions are Selenium-based transformations to perform.

The format of tests written using this library is

```
import state_machine_testing as smt

state_machine = smt.StateMachine()

t1 = state_machine.add_transition(transformation_func)
state_machine.add_state(t1, assertion_func)

state_machine.run()
```
