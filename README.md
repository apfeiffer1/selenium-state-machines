# State Machines for Selenium

[![Documentation Status](https://readthedocs.org/projects/selenium-state-machines/badge/?version=latest)](https://selenium-state-machines.readthedocs.io/en/latest/?badge=latest)



This is a small library that allows you run Selenium tests as state machines.

The general idea is that states are sets of assertions and transitions are Selenium-based transformations to perform.

Our documentation is [here](https://selenium-state-machines.readthedocs.io/en/latest/).

Here's an example of the library being used to test the [VyPRServer](http://github.com/pyvypr/VyPRServer/) web application.

```
import state_machine_testing as smt

def transition_1(runner):
    runner.driver().get("http://localhost:8080/")


def assertions_1(runner):
    driver = runner.driver()
    # selenium-based queries of the page
    assert something

state_machine = smt.StateMachine()

# set up state machine
t1 = state_machine.add_transition(load_main_page)
s1 = t1.set_target_state(assert_first_screen)

t2 = s1.add_outgoing_transition(choose_tab)
s2 = t2.set_target_state(assert_tab_selection)

[...]

t5 = s4.add_outgoing_transition(
    open_function_panel,
    guard=lambda runner : len(runner.store().get("buttons")) > 1
)
s5 = t5.set_target_state(assert_open_function_panel)

t6 = s5.add_outgoing_transition(choose_other_function)
s6 = t6.set_target_state(assert_other_function_selection)

state_machine.run()

state_machine.write_to_file("state-machine.gv")
```
