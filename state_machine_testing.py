"""
Small library for running selenium tests by defining interactions and assertions as a state-machine.

Interactions to be performed with the browser are represented by transitions.
Assertions are represented by states.
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from graphviz import Digraph
import traceback
from multiprocessing import Process, Queue


class StateMachineCollection(object):
    """
    Contains a list of StateMachine instances.
    Handles executing state machines and organising the results.
    """

    def __init__(self, machines):
        """
        Set up the initial list of state machines.
        """
        if type(machines) is list:
            self._state_machines = machines
        else:
            raise Exception("State machines must be given as a list instance.")

    def add_state_machine(self, machine):
        if type(machine) is StateMachine:
            self._state_machines.append(machine)
        else:
            raise Exception("Element to add to collection must be a StateMachine instance.")

    def run(self):
        """
        Execute each state machine and collect results.
        """
        for machine in self._state_machines:
            machine.run()


class StateMachineTransition(object):
    """
    Models a state machine transition.
    """

    def __init__(self, source_state, transition_function, guard=None):
        self._state_sequence_instance = None
        self._source_state = source_state
        self._target_state = None
        self._transition_function = transition_function
        self._guard = guard

    def __repr__(self):
        return "<StateMachineTransition %s>" % self._transition_function

    def get_function(self):
        return self._transition_function

    def get_guard(self):
        return self._guard

    def evaluate_guard(self, state_sequence_instance):
        """
        Evaluate this transition's guard with respect to a state sequence instance.
        """
        return self._guard(state_sequence_instance) if self._guard else True

    def execute(self, state_sequence_instance):
        """
        Execute self._transition_function to transform the state held in the state sequence instance,
        ready for assertions by the target state.
        """
        return self._transition_function(state_sequence_instance)

    def set_target_state(self, obj):
        """
        If ``obj`` is an instance of ``StateMachineState```, set as the target state.
        If ``obj`` is a callable, wrap in a ``StateMachineState`` object and set as the target state.
        """
        if type(obj) is not StateMachineState and callable(obj):
            # we've been given a function, so wrap it in a state object
            obj = StateMachineState(obj)
        self._target_state = obj
        return obj

    def get_target_state(self):
        return self._target_state


class StateMachineState(object):
    """
    Models a state machine state.
    """

    def __init__(self, assertion_function):
        self._state_sequence_instance = None
        self._assertion_function = assertion_function
        self._outgoing_transitions = []

    def __repr__(self):
        return "<StateMachineState %s>" % str(self._assertion_function)

    def get_function(self):
        return self._assertion_function

    def execute(self, state_sequence_instance):
        """
        Execute self._assertion_function to perform assertions on the state generated by the incoming transition.
        """
        result = self._assertion_function(state_sequence_instance)
        return result

    def add_outgoing_transition(self, obj, guard=None):
        """
        If ``obj`` is a ``StateMachineTransition`` instance, add to the outgoing transitions.
        If ``obj`` is callable, wrap in a ``StateMachineTransition`` instance and add to the outgoing transitions.
        ``guard`` is optional and must be a callable object that assumes its only argument will be a ``StateSequence``
        instance.
        """
        if guard and not callable(guard):
            raise Exception("Guard supplied to transition must be callable.")
        if type(obj) is not StateMachineTransition and callable(obj):
            # we've been given a function, so wrap it in a transition object
            obj = StateMachineTransition(self, obj, guard=guard)
        self._outgoing_transitions.append(obj)
        return obj

    def get_outgoing_transitions(self):
        return self._outgoing_transitions


class StateMachineStore(object):
    """
    Models a single state machine's data store for data shared across states and transitions.
    """

    def __init__(self):
        self._data = {}

    def put(self, key, value):
        self._data[key] = value

    def get(self, key):
        return self._data.get(key)


class StateMachine(object):
    """
    Models a single state machine.
    """

    def __init__(self):
        """
        Set up the initial configuration of the state machine.
        """
        self._start_state = StateMachineState(lambda fake_arg : True)
        self._states = [self._start_state]
        # when the state machine is run, the first step is to turn it into a list of
        # sequences that can be run one-by-one
        self._execution_sequences = []
        # set up testing reports
        self._state_sequence_to_result = {}
        # map state sequence objects to processes
        self._state_sequence_to_process = {}

    def __repr__(self):
        return "<StateMachine %s>" % self._start_state

    def get_states(self):
        return self._states

    def _get_state_set(self):
        """
        Stack-based traversal.
        """
        state_stack = [t.get_target_state() for t in self._start_state.get_outgoing_transitions()]
        final_state_set = [self._start_state]
        while len(state_stack) > 0:
            # get the top element from the stack
            current_state = state_stack.pop()
            # add the current state to the final set
            final_state_set.append(current_state)
            # add to stack of states we need to process
            state_stack += filter(
                lambda state : state not in final_state_set,
                map(lambda t : t.get_target_state(), current_state.get_outgoing_transitions())
            )
        return final_state_set

    def write_to_file(self, file_name):
        """
        Write the state machine to a graph file with the name ``file_name``.
        """

        graph = Digraph()
        graph.attr("graph", fontsize="10")
        shape = "Mrecord"
        font = "monaco"
        for state in self._get_state_set():
            graph.node(
                str(id(state)),
                str(state.get_function().__name__) if state.get_function().__name__ != "<lambda>" else "",
                shape=shape,
                fontname=font,
                color="black",
                fontcolor="black"
            )
            for transition in state.get_outgoing_transitions():
                graph.edge(
                    str(id(state)),
                    str(id(transition.get_target_state())),
                    transition.get_function().__name__,
                    fontname=font,
                    color="black",
                    fontcolor="black"
                )
        graph.render(file_name)

    def write_results_to_file(self, file_name):
        """
        Write the state machine to a graph file with the name ``file_name``, with colouring based on results.
        """
        # first, if it exists, derive the set of problematic edges
        report = self.get_state_sequence_results()
        problematic_transitions = []
        problematic_assertion_states = []

        for sequence_index in report:
            for result in report[sequence_index]:
                if not result["result"]:
                    # if there was a failure on this sequence, we register the incoming
                    # transition as problematic
                    failing_state = self._states[result["state_index"]]
                    incoming_transition = self._execution_sequences[result["sequence"]].\
                        get_incoming_transition(failing_state)
                    problematic_transitions.append(incoming_transition)
                    problematic_assertion_states.append(failing_state)

        graph = Digraph()
        graph.attr("graph", fontsize="10")
        shape = "Mrecord"
        font = "monaco"
        for state in self._get_state_set():
            graph.node(
                str(id(state)),
                str(state.get_function().__name__) if state.get_function().__name__ != "<lambda>" else "",
                shape=shape,
                fontname=font,
                color="red" if state in problematic_assertion_states else "darkgreen",
                fontcolor="red" if state in problematic_assertion_states else "darkgreen"
            )
            for transition in state.get_outgoing_transitions():
                graph.edge(
                    str(id(state)),
                    str(id(transition.get_target_state())),
                    transition.get_function().__name__,
                    fontname=font,
                    color="red" if transition in problematic_transitions else "darkgreen",
                    fontcolor="red" if transition in problematic_transitions else "darkgreen"
                )
        graph.render(file_name)

    def register_state_sequence_result(self, state_sequence_index, result):
        """
        Associate a state sequence instance index with information about its execution.
        """
        if self._state_sequence_to_result.get(state_sequence_index):
            self._state_sequence_to_result[state_sequence_index].append(result)
        else:
            self._state_sequence_to_result[state_sequence_index] = [result]

    def get_state_sequence_results(self):
        return self._state_sequence_to_result

    def run(self):
        """
        Run the state machine and display results.
        """
        # compute the set of states
        self._states = self._get_state_set()
        # populate the list of execution sequences
        self._recurse(self._start_state, [self._start_state])
        # map execution sequence to StateSequence instances
        self._execution_sequences = map(
            lambda (n, sequence) : StateSequence(self, sequence, n),
            enumerate(self._execution_sequences)
        )
        print("\nRUNNING TESTS...")
        central_queue = Queue()
        for sequence in self._execution_sequences:
            self._state_sequence_to_process[sequence] = Process(
                target=sequence.execute,
                args=(central_queue,)
            )
            self._state_sequence_to_process[sequence].start()

        # join all processes
        for sequence in self._execution_sequences:
            self._state_sequence_to_process[sequence].join()

        # get results
        while not central_queue.empty():
            top = central_queue.get()
            self.register_state_sequence_result(top["sequence"], top)

        print("...COMPLETE\n")

        # get results
        self._output_results()

    def _output_results(self):
        """
        Print test results after tests have been run.
        """
        print("\nRESULTS\n")
        results = self.get_state_sequence_results()
        for sequence_index in results:
            sequence = self._execution_sequences[sequence_index]
            print(sequence)
            for result in results[sequence_index]:
                print("  -- result from function '%s'" %
                      self._states[result["state_index"]].get_function().__name__)
                if result["result"]:
                    print("    -- success")
                else:
                    print("    -- failure")

    def _recurse(self, current_state, current_sequence):
        """
        Recurse on the state machine to determine the list of execution sequences that one can take.
        If we encounter a state that is already in the current sequence, then we are in a cycle so we end the sequence.
        Hence, the recursive base case is
            end the current branch of recursion if there are no outgoing transitions, once those which have already
            been traversed have been excluded.
        """
        if len(current_state.get_outgoing_transitions()) == 0:
            # recursive base case
            self._execution_sequences.append(current_sequence)
        else:
            # get all child states of the current state that haven't been encountered
            child_transitions = filter(
                lambda transition : transition.get_target_state() not in current_sequence,
                current_state.get_outgoing_transitions()
            )
            # get all child states that have already been encountered in the current sequence
            already_encountered = filter(
                lambda transition : transition.get_target_state() in current_sequence,
                current_state.get_outgoing_transitions()
            )
            # for each child state that is new
            for transition in child_transitions:
                # if there are multiple child states, copy the sequence for that branch of recursion
                # otherwise, use the existing one
                # in both cases append the child state to the sequence
                new_sequence = ([s for s in current_sequence]
                                if len(child_transitions) > 1
                                else current_sequence) + [transition.get_target_state()]
                self._recurse(transition.get_target_state(), new_sequence)

            # for each child state that is not new
            for transition in already_encountered:
                # recursive base case
                # add a copy of the current sequence for each case
                self._execution_sequences.append([s for s in current_sequence] + [transition.get_target_state()])

    def add_state(self, incoming_transition, assertion_function):
        """
        Add a state with the callable ``assertion_function`` to the state machine and set as the target state of
        ``incoming_transition``.
        Return an instance of the new state so that it can be used to add transitions.
        """

        if not callable(assertion_function):
            raise Exception("Object given as an assertion function for a new state must be callable.")

        new_state = StateMachineState(assertion_function)
        incoming_transition.set_target_state(new_state)
        return new_state

    def add_transition(self, transition_function, source_state=None, target_state=None, guard=None):
        """
        Add a transition with the ``transition_function`` leading out of ``source_state``.
        If ``target_state`` is given, it must be either a ``StateMachineState`` instance or a callable object.
        If a ``guard`` is given, it must be a callable object whose only argument is a ``StateSequence`` instance.
        Return an instance of the new transition so that it can be used to add new states.
        """

        if not callable(transition_function):
            raise Exception("Object given as a function to run during a transition must be callable.")

        if source_state and type(source_state) is not StateMachineState:
            raise Exception("Object given as transition source state must be a StateMachineState instance.")

        if guard and not callable(guard):
            raise Exception("Guard supplied to transition must be callable.")

        if not source_state:
            # if no source state is given, assume the transition is being added
            source_state = self._start_state

        new_transition = StateMachineTransition(source_state, transition_function, guard=guard)
        source_state.add_outgoing_transition(new_transition)
        if target_state:
            new_transition.set_target_state(target_state)
        return new_transition


class StateSequence(object):
    """
    Allows a single sequence of states derived from a state machine to be executed separately from all others.
    """

    def __init__(self, state_machine, sequence, label):
        # set up driver
        options = Options()
        options.headless = True
        # set up instance variables
        self._driver = webdriver.Firefox(options=options)
        self._store = StateMachineStore()
        self._label = label
        self._state_machine = state_machine
        # we are given a sequence of states, so we need to derive the transitions
        # from the state machine
        full_sequence = []
        for (n, state) in enumerate(sequence):
            full_sequence.append(state)
            # find the relevant transition
            if n < len(sequence)-1:
                next_transition = filter(
                    lambda transition : transition.get_target_state() == sequence[n+1],
                    state.get_outgoing_transitions()
                )[0]
                full_sequence.append(next_transition)
            else:
                break
        self._sequence = full_sequence

    def __repr__(self):
        return " -> ".join(
            map(
                lambda element : element.get_function().__name__,
                filter(lambda element : type(element) is StateMachineTransition, self._sequence)
            )[1:]
        )

    def driver(self):
        """
        Gets the browser driver associated with this sequence.
        """
        return self._driver

    def store(self):
        """
        Gets the ``StateMachineStore`` instance used as memory for this sequence.
        """
        return self._store

    def get_sequence(self):
        return self._sequence

    def get_incoming_transition(self, state):
        """
        Given a state from this sequence, get the transition between the preceding state and this one.
        """
        return self._sequence[self._sequence.index(state)-1]

    def execute(self, results_queue):
        """
        Execute the sequence of states/transitions.
        """
        # execute all elements' functions, missing out the first empty state
        for (n, element) in enumerate(self._sequence[1:]):
            # first, if the element is a transition, check it's guard
            if type(element) is StateMachineTransition and element.get_guard():
                if not element.evaluate_guard(self):
                    # if the guard fails, stop executing this sequence
                    break
            # execute the element's function with this state sequence object
            try:
                element.execute(self)
                if type(element) is StateMachineState:
                    results_queue.put({
                        "sequence" : self._label,
                        "state_index" : self._state_machine.get_states().index(element),
                        "result" : True
                    })
            except Exception as e:
                if type(element) is StateMachineState:
                    results_queue.put({
                        "sequence" : self._label,
                        "state_index": self._state_machine.get_states().index(element),
                        "result": False,
                        "exception" : traceback.format_exc()
                    })