"""
Attack Runtime for LR and Correlation Attacks on XOR Arbiter PUFs

We study the expected time until first success for
 - Logistic Regression and
 - Correlation
attacks on XOR Arbiter PUFs with the following input transformations:
 - Classic,
 - Lightweight Secure, and
 - Permutation.
The results are output as a LaTeX Table. For the correlation attack,
statistics are generated that provide further information about the
expected run time of the correlation attack.
"""
from datetime import timedelta
from typing import NamedTuple, Tuple

from math import ceil

from pypuf.experiments.experiment.correlation_attack import ExperimentCorrelationAttack
from pypuf.experiments.experiment.correlation_attack import Parameters as CorrelationAttackParameters
from pypuf.experiments.experiment.logistic_regression import ExperimentLogisticRegression
from pypuf.experiments.experiment.logistic_regression import Parameters as LogisticRegressionParameters
from pypuf.plots import PermutationIndexPlot
from pypuf.simulation.arbiter_based.ltfarray import LTFArray
from pypuf.studies.base import Study


def time_to_string(delta):
    """
    Converts the given time duration into a human readable string.
    :param delta: time duration in seconds
    """
    if delta.total_seconds() > 4 * 24 * 60 ** 2:
        return '%i days' % round(delta.days)
    else:
        hours = delta.seconds // 3600
        if 24 * delta.days + hours == 0:
            minutes = (delta.seconds - (3600 * hours)) // 60
            seconds = (delta.seconds - (3600 * hours) - (60 * minutes)) // 1
            return '%2im %02is' % (minutes, seconds)
        else:
            minutes = round((delta.seconds - (3600 * hours)) / 60)
            return '%2ih %02im' % (24 * delta.days + hours, minutes)


def round_time(seconds):
    """
    Rounds the given time duration.
    :param seconds: time duration in seconds
    """
    units = [
        4 * 24 * 60 ** 2,  # 4 days
        1,  # second
    ]
    for u in units:
        if seconds > u:
            return seconds // u * u
    return seconds


NICE_ATTACK_NAMES = {'lr': 'LR', 'corr': 'Correlation Attack'}
NICE_TRANSFORM_NAMES = {
    LTFArray.transform_atf.__name__: "Classic",
    LTFArray.transform_lightweight_secure.__name__: "Lightweight Secure",
    LTFArray.transform_fixed_permutation.__name__: "Permutation-Based"
}


class TableEntryParameters(NamedTuple):
    """
    Parameters for the experiments for the individual entries of the resulting run-time table.
    """
    n: int
    k: int
    N: int
    plot_layout: Tuple = None
    label: str = ""


class AttackRuntimeStudy(Study):
    """
    Study which generates a run-time table benchmarking different combinations of (n, k, N) for different
    transformations and attacks (pure lr vs. correlation attack). It also outputs a figure showing the index of the
    successful permutations for the correlation attack.
    """
    SAMPLES_PER_ENTRY = 1000

    PARAMETERS = [
        TableEntryParameters(64, 5, 300000, (2, 2, 1), 'Perm. Index. Dist. (n=64; k=5; 300,000 CRPs)'),
        TableEntryParameters(64, 6, 1000000, (2, 2, 2), 'Perm. Index. Dist. (n=64; k=6; 1,000,000 CRPs)'),
        TableEntryParameters(64, 7, 2000000),
        TableEntryParameters(128, 4, 1000000, (2, 2, 3), 'Perm. Index. Dist. (n=128; k=4; 2,000,000 CRPs)'),
        TableEntryParameters(128, 5, 2000000, (2, 2, 4), 'Perm. Index. Dist. (n=128; k=5; 2,000,000 CRPs)'),
    ]
    TRANSFORMATIONS = [LTFArray.transform_atf, LTFArray.transform_lightweight_secure,
                       LTFArray.transform_fixed_permutation]

    COMPRESSION = True

    def __init__(self):
        super().__init__()
        self.result_plot = None
        self.success_threshold = .98
        self.optimization_threshold = .65

        self.result_plot = PermutationIndexPlot(
            filename='figures/%s.fig_05.pdf' % self.name(),
            group_subplot_layout=self.PARAMETERS,
            w=3.34,
            h=1.5,
        )

    def gen_table(self, results):
        """
        Generate runtime/success comparison from data
        """
        columns = [
            ('lr', LTFArray.transform_atf.__name__),
            ('lr', LTFArray.transform_lightweight_secure.__name__),
            ('corr', LTFArray.transform_lightweight_secure.__name__),
            ('lr', LTFArray.transform_fixed_permutation.__name__),
            # ('lr', 'random'),
        ]
        latex = r'\begin{tabular}{rrr' + len(columns) * 'c' + '}\n  \\toprule\n'
        latex += r'  &&&'
        latex += '&\t\t'.join(
            [r'%s on' % NICE_ATTACK_NAMES[attack] for (attack, transform) in columns])
        latex += r'\\'
        latex += '\n'
        latex += r'  $n$ & $k$ & \# CRPs &' + '\t\t'
        latex += '&\t\t'.join(
            [r'%s' % NICE_TRANSFORM_NAMES[transform] for (attack, transform) in columns])
        latex += r'\\'
        latex += '\n  \\midrule\n'
        for p in self.PARAMETERS:
            latex += '  {:d}&{:d}&{:,d}&\t\t'.format(p.n, p.k, p.N)
            column_latex = []
            for (attack, transformation) in columns:
                sel = results.loc[(results['n'] == p.n) & (results['k'] == p.k) & (results['N'] == p.N)]
                if attack == 'corr':
                    sel = sel[sel['experiment'] == 'ExperimentCorrelationAttack']
                else:
                    sel = sel[(sel['transformation'] == transformation) &
                              (sel['experiment'] == 'ExperimentLogisticRegression')]
                if sel.empty:
                    column_latex.append(r'no data yet')
                    continue
                successful_runs = sel.loc[sel['accuracy'] > self.success_threshold]
                failed_runs = sel.loc[sel['accuracy'] <= self.success_threshold]
                success_rate = len(successful_runs) / len(sel)
                avg_wall_time = sel['measured_time'].mean()
                avg_no_success_wall_time = failed_runs['measured_time'].mean() if not failed_runs.empty else 0

                if success_rate > 0:
                    avg_success_wall_time = successful_runs['measured_time'].mean()
                    expected_tries_till_success = ceil(1 / success_rate)
                    expected_time_till_success = \
                        (expected_tries_till_success - 1) * avg_no_success_wall_time + avg_success_wall_time
                else:
                    expected_time_till_success = avg_wall_time * len(sel)

                marker = ''  # To include sample size, use marker = r'${}^{%d}$' % len(sel)

                if success_rate > 0:
                    column_latex.append(r'{}'.format(
                        time_to_string(timedelta(seconds=round_time(expected_time_till_success)))) + marker)
                else:
                    column_latex.append(r'(%s)${}^\ast$' % (
                        time_to_string(timedelta(seconds=round_time(expected_time_till_success)))) + marker)
            latex += '&\t\t'.join(column_latex)
            latex += r'\\' + '\n'

        latex += '  \\bottomrule\n'
        latex += r'\end{tabular}'

        runtime_table = open('figures/%s.table.tex' % self.name(), 'w')
        runtime_table.write(latex)
        runtime_table.close()

    def plot(self):
        results = self.experimenter.results

        self.gen_table(results)
        self.result_plot.plot(results)

    def experiments(self):
        experiments = []

        for i in range(self.SAMPLES_PER_ENTRY):
            for p in self.PARAMETERS:
                common_parameters = {
                    'n': p.n,
                    'k': p.k,
                    'N': p.N,
                    'seed_instance': 314159 + i,
                    'seed_model': 265358 + i,
                    'seed_challenge': 979323 + i,
                    'seed_distance': 846264 + i,
                    'mini_batch_size': 0,
                    'convergence_decimals': 2,
                    'shuffle': False
                }
                ex = ExperimentCorrelationAttack(
                    progress_log_prefix=self.name(),
                    parameters=CorrelationAttackParameters(
                        **common_parameters,
                        lr_iteration_limit=1000,
                    )
                )
                experiments.append(ex)
                for transform in self.TRANSFORMATIONS:
                    ex = ExperimentLogisticRegression(
                        progress_log_prefix=self.name(),
                        parameters=LogisticRegressionParameters(
                            **common_parameters,
                            transformation=transform.__name__,
                            combiner=LTFArray.combiner_xor.__name__,
                        )
                    )
                    experiments.append(ex)

        return experiments
