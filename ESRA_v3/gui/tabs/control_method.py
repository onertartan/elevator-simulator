"""
gui/tabs/control_method.py
===========================
Tab 3: 'Control Method'. Ported from the MATLAB source:

  * Control method radio group: Nearest Car Method,
    Metaheuristics (default), Exact Dispatcher, Markov Decision Process.
  * Objective Function dropdown (default 'Destination Information').
  * Metaheuristics panel:
      - Algorithm radios: Genetic Algorithm (default), Ant Colony
        Optimization, Particle Swarm Optimization, Differential Evolution.
      - Common: Population size [2..1000]=100, Max iterations [1..10000]=50.
      - GA: mutation rate 0.01, crossover rate 0.8, crossover fn
        (scattered default / singlepoint / twopoint), selection fn
        (stochunif default / roulette / tournament).
      - Mutation function group: scramble / block / uniform (default) /
        swap / frequency.
      - ACO: alpha=1 [0..5], rho=0.5 [0..1], Q=1 [1..100], beta=2 [0..5].
      - PSO: c1=c2=c3=0.8 [0..1], w_start=0.2 [0.1..1], w_end=0.2 [0..1]
        with the silent constraint w_end <= w_start.
      - DE: F=0.4 [0..1], CR=0.8 [0..1], variant dropdown (rand/1 default).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox, QRadioButton, QButtonGroup, QPushButton
)


def _dspin(minimum, maximum, value, decimals=2, step=0.05):
    b = QDoubleSpinBox()
    b.setRange(minimum, maximum)
    b.setDecimals(decimals)
    b.setSingleStep(step)
    b.setValue(value)
    b.setFixedWidth(90)
    return b


def _ispin(minimum, maximum, value):
    b = QSpinBox()
    b.setRange(minimum, maximum)
    b.setValue(value)
    b.setFixedWidth(90)
    return b


class ControlMethodTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        method_box = QGroupBox("Control Method")
        mb = QVBoxLayout(method_box)

        self.nearest_car_rb = QRadioButton("Nearest Car Method")
        self.metaheuristics_rb = QRadioButton("Metaheuristics")
        self.metaheuristics_rb.setChecked(True)  # default in MATLAB
        self.exact_rb = QRadioButton("Exact Dispatcher (Subset DP)")
        self.mdp_rb = QRadioButton("Markov Decision Process")
        method_group = QButtonGroup(self)
        for rb in (self.nearest_car_rb, self.metaheuristics_rb, self.exact_rb, self.mdp_rb):
            method_group.addButton(rb)
            mb.addWidget(rb)

        obj_row = QHBoxLayout()
        obj_row.addWidget(QLabel("Objective Function"))
        self.objective_function = QComboBox()
        self.objective_function.addItems([
            "Conventional Information", "Number of Passengers",
            "Destination Information", "User Defined 1",
            "User Defined 2", "User Defined 3"])
        self.objective_function.setCurrentText("Destination Information")
        obj_row.addWidget(self.objective_function)
        obj_row.addStretch()
        mb.addLayout(obj_row)
        layout.addWidget(method_box)

        self.exact_panel = QGroupBox("Exact assignment")
        exact = QVBoxLayout(self.exact_panel)
        limits = QHBoxLayout()
        limits.addWidget(QLabel("Maximum calls"))
        self.exact_max_calls = _ispin(1, 30, 16)
        limits.addWidget(self.exact_max_calls)
        limits.addWidget(QLabel("Time limit per decision (s)"))
        self.exact_time_limit = _dspin(0.001, 86400, 120, decimals=3, step=10)
        self.exact_time_limit.setFixedWidth(120)
        limits.addWidget(self.exact_time_limit)
        limits.addStretch()
        exact.addLayout(limits)
        exact_note = QLabel(
            "Minimizes estimated mean passenger waiting time to pickup door-opening start "
            "(Destination / WT). "
            "Optimization assumes unlimited capacity; simulation capacity is unchanged. "
            "Recommended: one-shot dispatch with no new arrivals. Repeated decisions "
            "can be expensive; snapshots during pending boarding are not supported. "
            "Timeouts stop the run without a heuristic fallback. Terminate cancels the solve.")
        exact_note.setWordWrap(True)
        exact.addWidget(exact_note)
        layout.addWidget(self.exact_panel)
        self._exact_active = False
        self._objective_before_exact = self.objective_function.currentText()

        # ---- Metaheuristics panel -----------------------------------------
        self.meta_box = QGroupBox("Metaheuristics")
        meta = QGridLayout(self.meta_box)
        meta.setHorizontalSpacing(24)

        self.ga_rb = QRadioButton("Genetic Algorithm")
        self.ga_rb.setChecked(True)  # default
        self.aco_rb = QRadioButton("Ant Colony Optimization")
        self.pso_rb = QRadioButton("Particle Swarm Optimization")
        self.de_rb = QRadioButton("Differential Evolution")
        algo_group = QButtonGroup(self)
        for i, rb in enumerate((self.ga_rb, self.aco_rb, self.pso_rb, self.de_rb)):
            algo_group.addButton(rb)
            meta.addWidget(rb, 0, i)

        # Common parameters
        common_row = QHBoxLayout()
        common_row.addWidget(QLabel("Population size"))
        self.population_size = _ispin(2, 1000, 100)
        common_row.addWidget(self.population_size)
        common_row.addSpacing(20)
        common_row.addWidget(QLabel("Maximum number of iterations"))
        self.max_iterations = _ispin(1, 10000, 50)
        common_row.addWidget(self.max_iterations)
        common_row.addStretch()
        meta.addLayout(common_row, 1, 0, 1, 4)

        # GA panel
        self.ga_panel = QGroupBox("GA")
        ga = QGridLayout(self.ga_panel)
        ga.addWidget(QLabel("Mutation rate"), 0, 0)
        self.ga_mutation_rate = _dspin(0, 1, 0.01, step=0.01)
        ga.addWidget(self.ga_mutation_rate, 0, 1)
        ga.addWidget(QLabel("Crossover rate"), 1, 0)
        self.ga_crossover_rate = _dspin(0, 1, 0.8)
        ga.addWidget(self.ga_crossover_rate, 1, 1)

        crossover_box = QGroupBox("Crossover function")
        cb = QVBoxLayout(crossover_box)
        self.crossover_scattered = QRadioButton("crossoverscattered")
        self.crossover_scattered.setChecked(True)
        self.crossover_singlepoint = QRadioButton("crossoversinglepoint")
        self.crossover_twopoint = QRadioButton("crossovertwopoint")
        cross_group = QButtonGroup(self)
        for rb in (self.crossover_scattered, self.crossover_singlepoint,
                   self.crossover_twopoint):
            cross_group.addButton(rb)
            cb.addWidget(rb)
        ga.addWidget(crossover_box, 0, 2, 2, 1)

        selection_box = QGroupBox("Selection function")
        sb = QVBoxLayout(selection_box)
        self.selection_stochunif = QRadioButton("selectionstochunif")
        self.selection_stochunif.setChecked(True)
        self.selection_roulette = QRadioButton("selectionroulette")
        self.selection_tournament = QRadioButton("selectiontournament")
        sel_group = QButtonGroup(self)
        for rb in (self.selection_stochunif, self.selection_roulette,
                   self.selection_tournament):
            sel_group.addButton(rb)
            sb.addWidget(rb)
        ga.addWidget(selection_box, 0, 3, 2, 1)
        self.ga_search_button = QPushButton("Run GA Parameter Search...")
        ga.addWidget(self.ga_search_button, 2, 0, 1, 4)
        meta.addWidget(self.ga_panel, 2, 0, 1, 4)

        # Mutation function group (shared, per MATLAB startData)
        mutation_box = QGroupBox("Mutation function")
        mub = QHBoxLayout(mutation_box)
        self.mutation_scramble = QRadioButton("scramble")
        self.mutation_block = QRadioButton("block")
        self.mutation_uniform = QRadioButton("uniform")
        self.mutation_uniform.setChecked(True)
        self.mutation_swap = QRadioButton("swap")
        self.mutation_frequency = QRadioButton("frequency")
        mut_group = QButtonGroup(self)
        for rb in (self.mutation_scramble, self.mutation_block,
                   self.mutation_uniform, self.mutation_swap,
                   self.mutation_frequency):
            mut_group.addButton(rb)
            mub.addWidget(rb)
        mub.addStretch()
        meta.addWidget(mutation_box, 3, 0, 1, 4)

        # ACO panel
        self.aco_panel = QGroupBox("ACO")
        aco = QHBoxLayout(self.aco_panel)
        self.aco_alpha = _dspin(0, 5, 1)
        self.aco_rho = _dspin(0, 1, 0.5)
        self.aco_q = _ispin(1, 100, 1)
        self.aco_beta = _dspin(0, 5, 2)
        for label, w in (("\u03b1", self.aco_alpha), ("\u03c1", self.aco_rho),
                         ("Q", self.aco_q), ("\u03b2", self.aco_beta)):
            aco.addWidget(QLabel(label))
            aco.addWidget(w)
        aco.addStretch()
        meta.addWidget(self.aco_panel, 4, 0, 1, 4)

        # PSO panel
        self.pso_panel = QGroupBox("PSO")
        pso = QHBoxLayout(self.pso_panel)
        self.pso_c1 = _dspin(0, 1, 0.8)
        self.pso_c2 = _dspin(0, 1, 0.8)
        self.pso_c3 = _dspin(0, 1, 0.8)
        self.pso_w_start = _dspin(0.1, 1, 0.2)
        self.pso_w_end = _dspin(0, 1, 0.2)
        for label, w in (("c1", self.pso_c1), ("c2", self.pso_c2),
                         ("c3", self.pso_c3), ("w_start", self.pso_w_start),
                         ("w_end", self.pso_w_end)):
            pso.addWidget(QLabel(label))
            pso.addWidget(w)
        pso.addStretch()
        meta.addWidget(self.pso_panel, 5, 0, 1, 4)

        # DE panel
        self.de_panel = QGroupBox("DE")
        de = QHBoxLayout(self.de_panel)
        self.de_f = _dspin(0, 1, 0.4)
        self.de_crossover_rate = _dspin(0, 1, 0.8)
        self.de_variant = QComboBox()
        self.de_variant.addItems(["rand/1", "best/1", "rand/2", "best/2",
                                  "current-to-best/1", "rand-to-best/1",
                                  "current-to-rand/1"])
        for label, w in (("F", self.de_f), ("CR", self.de_crossover_rate),
                         ("Variant", self.de_variant)):
            de.addWidget(QLabel(label))
            de.addWidget(w)
        de.addStretch()
        meta.addWidget(self.de_panel, 6, 0, 1, 4)

        layout.addWidget(self.meta_box)
        layout.addStretch()

        # ---- wiring ---------------------------------------------------------
        # w_end <= w_start silent constraint (psoWstart/psoWend callbacks)
        self.pso_w_start.valueChanged.connect(self._sync_w_end)
        self.pso_w_end.valueChanged.connect(self._sync_w_end)
        # enable/disable algorithm sub-panels
        for rb in (self.ga_rb, self.aco_rb, self.pso_rb, self.de_rb):
            rb.toggled.connect(self._update_algo_panels)
        for rb in (self.nearest_car_rb, self.metaheuristics_rb, self.exact_rb, self.mdp_rb):
            rb.toggled.connect(self._update_method_panels)
        self._update_algo_panels()
        self._update_method_panels()

    def _update_method_panels(self):
        exact = self.exact_rb.isChecked()
        if exact and not self._exact_active:
            self._objective_before_exact = self.objective_function.currentText()
            self.objective_function.setCurrentText("Destination Information")
        elif not exact and self._exact_active:
            self.objective_function.setCurrentText(self._objective_before_exact)
        self._exact_active = exact
        self.objective_function.setEnabled(not exact)
        self.exact_panel.setVisible(exact)
        self.meta_box.setEnabled(self.metaheuristics_rb.isChecked())
        self.meta_box.setVisible(not exact)

    def _sync_w_end(self):
        if self.pso_w_end.value() > self.pso_w_start.value():
            self.pso_w_end.setValue(self.pso_w_start.value())

    def _update_algo_panels(self):
        self.ga_panel.setEnabled(self.ga_rb.isChecked())
        self.aco_panel.setEnabled(self.aco_rb.isChecked())
        self.pso_panel.setEnabled(self.pso_rb.isChecked())
        self.de_panel.setEnabled(self.de_rb.isChecked())

    # ---- accessors --------------------------------------------------------
    def _selected_text(self, buttons):
        for rb in buttons:
            if rb.isChecked():
                return rb.text()
        return ""

    def to_start_data(self):
        data = {"objectiveFunction": self.objective_function.currentText()}
        if self.nearest_car_rb.isChecked():
            data.update({"controlMethod": "NearestCar",
                         "stateUpdateTypeForNextDecision": "fixed",
                         "availableInformation": 1})
        elif self.exact_rb.isChecked():
            data.update({"controlMethod": "Exact",
                         "objectiveFunction": "Destination Information",
                         "stateUpdateTypeForNextDecision": "fixed",
                         "availableInformation": 1,
                         "exactMaxCalls": self.exact_max_calls.value(),
                         "exactTimeLimitSeconds": self.exact_time_limit.value()})
        elif self.metaheuristics_rb.isChecked():
            data.update({
                "controlMethod": "Metaheuristics",
                "stateUpdateTypeForNextDecision": "fixed",
                "availableInformation": 1,
                "G": self.max_iterations.value(),
                "nPop": self.population_size.value(),
                "mutationFunction": self._selected_text(
                    (self.mutation_scramble, self.mutation_block,
                     self.mutation_uniform, self.mutation_swap,
                     self.mutation_frequency)),
            })
            if self.ga_rb.isChecked():
                data.update({
                    "algorithm": "GA",
                    "Pc": self.ga_crossover_rate.value(),
                    "Pm": self.ga_mutation_rate.value(),
                    "crossoverFcn": self._selected_text(
                        (self.crossover_scattered, self.crossover_singlepoint,
                         self.crossover_twopoint)),
                    "selectionFcn": self._selected_text(
                        (self.selection_stochunif, self.selection_roulette,
                         self.selection_tournament)),
                })
            elif self.aco_rb.isChecked():
                data.update({"algorithm": "ACO",
                             "alpha": self.aco_alpha.value(),
                             "rho": self.aco_rho.value(),
                             "Q": self.aco_q.value(),
                             "beta": self.aco_beta.value()})
            elif self.pso_rb.isChecked():
                data.update({"algorithm": "PSO",
                             "w_start": self.pso_w_start.value(),
                             "w_end": self.pso_w_end.value(),
                             "c1": self.pso_c1.value(),
                             "c2": self.pso_c2.value(),
                             "c3": self.pso_c3.value()})
            elif self.de_rb.isChecked():
                data.update({"algorithm": "DE",
                             "F": self.de_f.value(),
                             "crossoverRate": self.de_crossover_rate.value(),
                             "variant": self.de_variant.currentText()})
        else:
            data.update({"controlMethod": "MDP",
                         "stateUpdateTypeForNextDecision": "flexible"})
        return data

    def to_state(self):
        return {
            "method": ("nearest" if self.nearest_car_rb.isChecked()
                       else "meta" if self.metaheuristics_rb.isChecked()
                       else "exact" if self.exact_rb.isChecked()
                       else "mdp"),
            "objective_function": self.objective_function.currentText(),
            "objective_before_exact": self._objective_before_exact,
            "exact_max_calls": self.exact_max_calls.value(),
            "exact_time_limit": self.exact_time_limit.value(),
            "algorithm": ("GA" if self.ga_rb.isChecked() else
                          "ACO" if self.aco_rb.isChecked() else
                          "PSO" if self.pso_rb.isChecked() else "DE"),
            "population_size": self.population_size.value(),
            "max_iterations": self.max_iterations.value(),
            "ga_mutation_rate": self.ga_mutation_rate.value(),
            "ga_crossover_rate": self.ga_crossover_rate.value(),
            "crossover_fcn": self._selected_text(
                (self.crossover_scattered, self.crossover_singlepoint,
                 self.crossover_twopoint)),
            "selection_fcn": self._selected_text(
                (self.selection_stochunif, self.selection_roulette,
                 self.selection_tournament)),
            "mutation_fcn": self._selected_text(
                (self.mutation_scramble, self.mutation_block,
                 self.mutation_uniform, self.mutation_swap,
                 self.mutation_frequency)),
            "aco": [self.aco_alpha.value(), self.aco_rho.value(),
                    self.aco_q.value(), self.aco_beta.value()],
            "pso": [self.pso_c1.value(), self.pso_c2.value(),
                    self.pso_c3.value(), self.pso_w_start.value(),
                    self.pso_w_end.value()],
            "de": [self.de_f.value(), self.de_crossover_rate.value(),
                   self.de_variant.currentText()],
        }

    def from_state(self, s):
        {"nearest": self.nearest_car_rb, "meta": self.metaheuristics_rb,
         "exact": self.exact_rb, "mdp": self.mdp_rb}[s["method"]].setChecked(True)
        self._objective_before_exact = s.get("objective_before_exact", s["objective_function"])
        self.objective_function.setCurrentText(
            "Destination Information" if self.exact_rb.isChecked() else s["objective_function"])
        self.exact_max_calls.setValue(s.get("exact_max_calls", 16))
        self.exact_time_limit.setValue(s.get("exact_time_limit", 120.0))
        {"GA": self.ga_rb, "ACO": self.aco_rb,
         "PSO": self.pso_rb, "DE": self.de_rb}[s["algorithm"]].setChecked(True)
        self.population_size.setValue(s["population_size"])
        self.max_iterations.setValue(s["max_iterations"])
        self.ga_mutation_rate.setValue(s["ga_mutation_rate"])
        self.ga_crossover_rate.setValue(s["ga_crossover_rate"])
        for rb in (self.crossover_scattered, self.crossover_singlepoint,
                   self.crossover_twopoint):
            rb.setChecked(rb.text() == s["crossover_fcn"])
        for rb in (self.selection_stochunif, self.selection_roulette,
                   self.selection_tournament):
            rb.setChecked(rb.text() == s["selection_fcn"])
        for rb in (self.mutation_scramble, self.mutation_block,
                   self.mutation_uniform, self.mutation_swap,
                   self.mutation_frequency):
            rb.setChecked(rb.text() == s["mutation_fcn"])
        self.aco_alpha.setValue(s["aco"][0])
        self.aco_rho.setValue(s["aco"][1])
        self.aco_q.setValue(int(s["aco"][2]))
        self.aco_beta.setValue(s["aco"][3])
        self.pso_c1.setValue(s["pso"][0])
        self.pso_c2.setValue(s["pso"][1])
        self.pso_c3.setValue(s["pso"][2])
        self.pso_w_start.setValue(s["pso"][3])
        self.pso_w_end.setValue(s["pso"][4])
        self.de_f.setValue(s["de"][0])
        self.de_crossover_rate.setValue(s["de"][1])
        self.de_variant.setCurrentText(s["de"][2])
