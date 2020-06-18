# State Machines for Selenium

This is a small library that allows you run Selenium tests as state machines.

The general idea is that states are sets of assertions and transitions are Selenium-based transformations to perform.

The format of tests written using this library is

```
import state_machine_testing as smt

def transition_1(runner):
    runner.driver().get("http://localhost:8080/")


def assertions_1(runner):
    driver = runner.driver()
    # selenium-based queries of the page
    assert something

state_machine = smt.StateMachine()

t1 = state_machine.add_transition(transition_1)
state_machine.add_state(t1, assertions_1)

state_machine.run()
```
