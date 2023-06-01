import re
import warnings
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import argrelextrema
import scipy.constants as scpc


warnings.filterwarnings("ignore", category=RuntimeWarning)


def ev_to_lambda(ev):
    """Convert photon energies from eV to a wavelength in nm."""
    wavelength = ((scpc.h * scpc.c) / (ev * scpc.electron_volt)) * 10e8
    return wavelength


def lambda_to_ev(lambda_float):
    """Convert photon energies from a wavelength in nm to eV."""
    electronvolts = (10e8 * (scpc.h * scpc.c)) / (
        lambda_float * scpc.electron_volt
    )
    return electronvolts


def cutoff_transitions(dictionary, cutoff, ind_xmin, ind_xmax):
    """Output a list of transitions from a dict, with any that fall below a percentage cutoff of
    the maximum value transition set to None."""
    max_abs_val = {
        key: np.max(abs(val[ind_xmin:ind_xmax]))
        for key, val in dictionary.items()
    }
    max_val = max(max_abs_val.values())
    relevant_transition_list = []
    for transition, value in max_abs_val.items():
        if value >= (max_val * cutoff):
            relevant_transition_list += [transition]
        else:
            relevant_transition_list += [None]
    return relevant_transition_list


class TASPlotter:
    """
    Class to generate a matplotlib plot of the TAS or JDOS spectra, with a specific energy
    mesh, material, and conditions.

    Args:
        container: TAS container class as generated by TASGenerator().generate_tas().
        material_name: Name of material being investigated (string) [optional, for labelling]
    """

    def __init__(
        self,
        container,
        material_name=None,
    ):
        self.tas_total = container.tas_total
        self.jdos_diff_if = container.jdos_diff_if
        self.jdos_light_total = container.jdos_light_total
        self.jdos_light_if = container.jdos_light_if
        self.jdos_dark_total = container.jdos_dark_total
        self.jdos_dark_if = container.jdos_dark_if
        self.energy_mesh_ev = container.energy_mesh_ev
        self.bandgap = container.bandgap
        self.material_name = material_name
        self.temp = container.temp
        self.conc = container.conc
        self.energy_mesh_lambda = ev_to_lambda(self.energy_mesh_ev)
        self.bandgap_lambda = ev_to_lambda(self.bandgap)

        self.alpha_dark = container.alpha_dark
        self.alpha_light_dict = container.alpha_light_dict
        self.weighted_jdos_light_if = container.weighted_jdos_light_if
        self.weighted_jdos_dark_if = container.weighted_jdos_dark_if
        self.weighted_jdos_diff_if = container.weighted_jdos_diff_if

    def get_plot(
        self,
        relevant_transitions="auto",
        xaxis="wavelength",
        transition_cutoff=0.03,
        xmin=None,
        xmax=None,
        ymin=None,
        ymax=None,
        yaxis="tas",
        **kwargs,
    ):
        """
        Plots TAS spectra using the data generated in the TAS container class as generated by
        TASGenerator().generate_tas(). If the TASGenerator was not generated from VASP outputs,
        then the output TAS is generated using the change in joint density of states (JDOS) under
        illumination, with no consideration of oscillator strengths ("Total TAS (ΔJDOS only)") –
        this behaviour can also be explicitly chosen by setting "yaxis" to "jdos_diff".

        Otherwise, the output TAS is generated considering all contributions to the predicted TAS
        spectrum ("Total TAS (Δɑ)"). If only the contribution from the change in absorption is
        desired, with stimulated emission neglected, set "yaxis" to "tas_absorption_only".

        One can also plot the JDOS before and after illumination, by setting "yaxis" to "jdos",
        or the effective absorption coefficient (α, including absorption and stimulated emission)
        before and after illumination, by setting "yaxis" to "alpha".

        The individual band-to-band transitions which contribute to the JDOS/TAS are also shown
        (which can be controlled with the `transition_cutoff` argument – set to 1 to not show any
        band-band transitions), and these are weighted by the oscillator strength of the transition
        when TASGenerator was created from VASP objects and yaxis="tas", "tas_absorption_only" or
        "alpha".

        Args:
            relevant_transitions: List containing individual transitions to be displayed
                in the plot alongside the total plot. If material is not spin-polarised,
                only write the bands involved [(-1,6),(2,7),(-8,-5)...] If spin-polarised,
                include the type of spin involved in transition
                [(-1,6, "down"),(2,7, "down"),(-8,-5, "up")...]
                Default is 'auto' mode, which shows all band transitions above the
                transition_cutoff. Note that band-band transitions with overlapping extrema are
                scaled by 95% to avoid overlapping lines.
            xaxis: Units for the energy mesh. Either "wavelength" or "energy".
            transition_cutoff: The minimum height of the band transition as a percentage
                threshold of the largest contributing transition (Across all kpoints, within the
                energy range specified). Default is 0.03 (3%).
            xmin: Minimum energy point in mesh (float64)
            xmax: Maximum energy point in mesh (float64)
            ymin: Minimum absorption point. Default is 1.15 * minimum point.
            ymax: Maximum absorption point. Default is 1.15 * maximum point.
            yaxis: What spectral data to plot. If yaxis = "tas" (default), will plot the
                predicted TAS spectrum considering all contributions to the TAS (if TASGenerator
                was created from VASP outputs)("Total TAS (Δɑ)"), or just using the change in the
                joint density of states (JDOS) before & after illumination ("Total TAS (ΔJDOS
                only)") – the latter can also be explicitly selected with yaxis = "jdos_diff".

                If yaxis = "tas_absorption_only", will instead plot the predicted TAS spectrum
                considering only the change in absorption, with stimulated emission neglected.
                If yaxis = "jdos", will plot the joint density of states before & after
                illumination.
                If yaxis = "alpha", will plot the effective absorption coefficient (α, including
                absorption and stimulated emission) before and after illumination.
            **kwargs: Additional arguments to be passed to matplotlib.pyplot.legend(); such as
                `ncols` (number of columns in the legend), `loc` (location of the legend),
                `fontsize` etc. (see https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot
                .legend.html)

        Returns:
            Matplotlib pyplot of the desired spectrum, with labelled units.
        """
        # check specified yaxis matches available choices:
        if yaxis.lower() not in [
            "tas",
            "tas_absorption_only",
            "jdos",
            "alpha",
            "jdos_diff",
        ]:
            raise ValueError(
                f"Invalid yaxis '{yaxis}' specified, must be one of: 'tas', "
                f"'tas_absorption_only', 'jdos', 'alpha', 'jdos_diff'!"
            )

        energy_mesh = 0
        bg = 0
        plt.figure(figsize=(12, 8))

        xmin_ind = 0
        xmax_ind = -1

        if xaxis == "wavelength":
            energy_mesh = self.energy_mesh_lambda
            if xmin is not None:
                xmax_ind = np.abs(energy_mesh - xmin).argmin()
            if xmax is not None:
                xmin_ind = np.abs(energy_mesh - xmax).argmin()
            bg = self.bandgap_lambda
            plt.xlabel("Wavelength (nm)", fontsize=30)

        elif xaxis == "energy":
            energy_mesh = self.energy_mesh_ev
            if xmin is not None:
                xmin_ind = np.abs(energy_mesh - xmin).argmin()
            if xmax is not None:
                xmax_ind = np.abs(energy_mesh - xmax).argmin()
            bg = self.bandgap
            plt.xlabel("Energy (eV)", fontsize=30)

        if xmin is not None:
            if xmin / np.min(energy_mesh) < 0.95:
                raise ValueError(
                    "Plotting region xmin value is smaller than energy mesh minimum. Please "
                    "specify in same units as xaxis"
                )
            if xmin / np.max(energy_mesh) > 1.05:
                raise ValueError(
                    "Plotting region xmin value is larger than energy mesh maximum. Please "
                    "specify in same units as xaxis"
                )

        if xmax is not None:
            if xmax / np.min(energy_mesh) < 0.95:
                raise ValueError(
                    "Plotting region xmax value is smaller than energy mesh minimum. Please "
                    "specify in same units as xaxis"
                )
            if xmax / np.max(energy_mesh) > 1.05:
                raise ValueError(
                    "Plotting region xmax value is larger than energy mesh maximum. Please "
                    "specify in same units as xaxis"
                )

        def _rescale_overlapping_curves(list_of_curves):
            local_extrema_coords = []
            output_list_of_curves = []
            # get max value of all curves to use as relative scaling factor:
            max_curve = np.max([np.max(np.abs(curve)) for curve in list_of_curves if curve is not None])
            for curve in list_of_curves:  # Find the local maxima of each curve
                if curve is not None and np.max(np.abs(curve))/max_curve > 0.05:
                    local_extrema_indices = argrelextrema(
                        np.abs(curve), np.greater
                    )[0]
                    relative_local_extrema = [
                        (idx, round(np.abs(curve)[idx]/max_curve, 2))
                        for idx in local_extrema_indices
                    ]
                    # if any matching tuple in the list of local extrema:
                    while any(
                        i == j
                        for i in relative_local_extrema
                        for j in local_extrema_coords
                        if i[1]/max_curve > 0.05 and j[1]/max_curve > 0.05
                    ):
                        curve *= 0.95
                        local_extrema_indices = argrelextrema(
                            np.abs(curve), np.greater
                        )[0]
                        relative_local_extrema = [
                            (i, round(np.abs(curve)[i]/max_curve, 2))
                            for i in local_extrema_indices
                        ]

                    local_extrema_coords += [
                        (i, round(np.abs(curve)[i]/max_curve, 2))
                        for i in local_extrema_indices
                    ]
                output_list_of_curves.append(curve)

            return output_list_of_curves

        if yaxis.lower() in [
            "tas",
            "tas_absorption_only",
            "jdos_diff",
            "alpha",
        ]:
            abs_label = "ΔA (a.u.)"

            if (
                self.alpha_light_dict is not None
                and "jdos_diff" not in yaxis.lower()
            ):
                transition_dict = {
                    k: v
                    / np.max(
                        np.abs(list(self.weighted_jdos_diff_if.values()))[
                            xmin_ind:xmax_ind
                        ]
                    )
                    for k, v in self.weighted_jdos_diff_if.items()
                }
                if "tas" in yaxis.lower():
                    if yaxis.lower() == "tas_absorption_only":
                        tas_total = (
                            self.alpha_light_dict["absorption"]
                            - self.alpha_dark
                        )
                    else:  # yaxis = "tas"
                        tas_total = (
                            self.tas_total
                        )  # alpha_light_abs - alpha_light_emission - alpha_dark

                    normalised_tas = tas_total / np.max(
                        np.abs(tas_total)[xmin_ind:xmax_ind]
                    )
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        normalised_tas[xmin_ind:xmax_ind],
                        label="Total TAS (Δα)",
                        color="black",
                        lw=3.5,
                        alpha=0.75,  # make semi-transparent to show if overlapping lines
                    )

                else:  # yaxis = "alpha"
                    abs_label = "α (a.u.)"
                    transition_dict = (
                        {}
                    )  # control transition plotting here rather than later on:
                    alpha_normalisation_factor = (
                        np.max(  # normalise to max alpha in dark
                            np.abs(self.alpha_dark)[xmin_ind:xmax_ind]
                        )
                    )
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        (
                            self.alpha_light_dict["absorption"][
                                xmin_ind:xmax_ind
                            ]
                            - self.alpha_light_dict["emission"][
                                xmin_ind:xmax_ind
                            ]
                        )
                        / alpha_normalisation_factor,
                        label="α (light)",
                        color="black",
                        lw=2.5,
                        alpha=0.75,  # make semi-transparent to show if overlapping lines
                    )
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        self.alpha_dark[xmin_ind:xmax_ind]
                        / alpha_normalisation_factor,
                        label="α (dark)",
                        color="blue",
                        lw=2.5,
                        alpha=0.75,  # make semi-transparent to show if overlapping lines
                    )
                    weighted_jdos_normalisation_factor = np.max(
                        np.abs(list(self.weighted_jdos_dark_if.values()))[
                            xmin_ind:xmax_ind
                        ]
                    )

                    if relevant_transitions == "auto":
                        relevant_transition_list = cutoff_transitions(
                            self.weighted_jdos_light_if,
                            transition_cutoff,
                            xmin_ind,
                            xmax_ind,
                        )
                        list_of_curves = [
                            np.array(
                                self.weighted_jdos_light_if[transition][
                                    xmin_ind:xmax_ind
                                ]
                            )
                            if transition is not None
                            else None
                            for transition in relevant_transition_list
                        ]
                        list_of_curves = _rescale_overlapping_curves(
                            list_of_curves
                        )

                        for i, transition in enumerate(
                            relevant_transition_list
                        ):
                            if transition is not None:
                                plt.plot(
                                    energy_mesh[xmin_ind:xmax_ind],
                                    list_of_curves[i]
                                    / weighted_jdos_normalisation_factor,
                                    label=str(transition) + " (light)",
                                    color=f"C{2 * i}",
                                    lw=2.5,
                                )
                            if transition is not None and np.any(
                                self.weighted_jdos_dark_if[transition][
                                    xmin_ind:xmax_ind
                                ]
                            ):
                                # only plot dark if it's not all zero
                                plt.plot(
                                    energy_mesh[xmin_ind:xmax_ind],
                                    self.weighted_jdos_dark_if[transition][
                                        xmin_ind:xmax_ind
                                    ]
                                    / weighted_jdos_normalisation_factor,
                                    label=str(transition) + " (dark)",
                                    ls="--",  # dashed linestyle for dark to distinguish
                                    color=f"C{2 * i + 1}",
                                )

                    else:
                        list_of_curves = [
                            np.array(
                                self.weighted_jdos_light_if[transition][
                                    xmin_ind:xmax_ind
                                ]
                            )
                            if transition in relevant_transitions
                            else None
                            for transition in self.weighted_jdos_light_if.keys()
                        ]
                        list_of_transitions = [
                            transition
                            if transition in relevant_transitions
                            else None
                            for transition in self.weighted_jdos_light_if.keys()
                        ]
                        list_of_curves = _rescale_overlapping_curves(
                            list_of_curves
                        )

                        for i, transition in enumerate(list_of_transitions):
                            if transition is not None:
                                plt.plot(
                                    energy_mesh[xmin_ind:xmax_ind],
                                    list_of_curves[i]
                                    / weighted_jdos_normalisation_factor,
                                    label=str(transition) + " (light)",
                                    lw=2.5,
                                    color=f"C{2 * i}",
                                )
                                if np.any(
                                    self.weighted_jdos_dark_if[transition][
                                        xmin_ind:xmax_ind
                                    ]
                                ):
                                    # only plot dark if it's not all zero
                                    plt.plot(
                                        energy_mesh[xmin_ind:xmax_ind],
                                        self.weighted_jdos_dark_if[transition][
                                            xmin_ind:xmax_ind
                                        ]
                                        / weighted_jdos_normalisation_factor,
                                        label=str(transition) + " (dark)",
                                        ls="--",  # dashed linestyle for dark to distinguish
                                        color=f"C{2 * i + 1}",
                                    )

            else:
                if yaxis.lower() in ["tas_absorption_only", "alpha"]:
                    raise ValueError(
                        f"The `{yaxis}` option for yaxis can only be chosen if the TASGenerator "
                        f"object was created using VASP outputs!"
                    )

                if yaxis.lower() == "jdos_diff" and self.alpha_dark is not None:
                    # jdos_diff explicitly set but WAVEDER info parsed, so tas_total is not the jdos_diff:
                    jdos_diff = self.jdos_light_total - self.jdos_dark_total
                else:
                    jdos_diff = self.tas_total

                plt.plot(
                    energy_mesh[xmin_ind:xmax_ind],
                    jdos_diff[xmin_ind:xmax_ind],
                    label="Total TAS (ΔJDOS only)",
                    color="black",
                    lw=3.5,
                    alpha=0.75,  # make semi-transparent to show if overlapping lines
                )
                transition_dict = self.jdos_diff_if

            if (
                relevant_transitions == "auto" and transition_dict
            ):  # if transitions haven't already been plotted
                relevant_transition_list = cutoff_transitions(
                    transition_dict,
                    transition_cutoff,
                    xmin_ind,
                    xmax_ind,
                )
                list_of_curves = [
                    np.array(transition_dict[transition][xmin_ind:xmax_ind])
                    if transition is not None
                    else None
                    for transition in relevant_transition_list
                ]
                list_of_curves = _rescale_overlapping_curves(list_of_curves)

                for i, transition in enumerate(relevant_transition_list):
                    if transition is not None:
                        plt.plot(
                            energy_mesh[xmin_ind:xmax_ind],
                            list_of_curves[i],
                            label=str(transition),
                            lw=2.5,
                            color=f"C{i}",
                        )

            elif (
                transition_dict
            ):  # if transitions haven't already been plotted
                list_of_curves = [
                    np.array(transition_dict[transition][xmin_ind:xmax_ind])
                    if transition in relevant_transitions
                    else None
                    for transition in transition_dict.keys()
                ]
                list_of_transitions = [
                    transition if transition in relevant_transitions else None
                    for transition in self.jdos_light_if.keys()
                ]
                list_of_curves = _rescale_overlapping_curves(list_of_curves)

                for i, transition in enumerate(list_of_transitions):
                    if transition is not None:
                        plt.plot(
                            energy_mesh[xmin_ind:xmax_ind],
                            list_of_curves[i],
                            label=str(transition),
                            lw=2.5,
                            color=f"C{i}",
                        )

        elif yaxis.lower() == "jdos":
            abs_label = "JDOS (a.u.)"
            plt.plot(
                energy_mesh[xmin_ind:xmax_ind],
                self.jdos_light_total[xmin_ind:xmax_ind],
                label="JDOS (light)",
                color="black",
                lw=2.5,
                alpha=0.75,  # make semi-transparent to show if overlapping lines
            )
            plt.plot(
                energy_mesh[xmin_ind:xmax_ind],
                self.jdos_dark_total[xmin_ind:xmax_ind],
                label="JDOS (dark)",
                color="blue",
                lw=2.5,
                alpha=0.75,  # make semi-transparent to show if overlapping lines
            )

            if relevant_transitions == "auto":
                relevant_transition_list = cutoff_transitions(
                    self.jdos_light_if,
                    transition_cutoff,
                    xmin_ind,
                    xmax_ind,
                )
                list_of_curves = [
                    np.array(self.jdos_light_if[transition][xmin_ind:xmax_ind])
                    if transition is not None
                    else None
                    for transition in relevant_transition_list
                ]
                list_of_curves = _rescale_overlapping_curves(list_of_curves)

                for i, transition in enumerate(relevant_transition_list):
                    if transition is not None:
                        plt.plot(
                            energy_mesh[xmin_ind:xmax_ind],
                            list_of_curves[i],
                            label=str(transition) + " (light)",
                            color=f"C{2*i}",
                            lw=2.5,
                        )
                        if np.any(
                            self.jdos_dark_if[transition][xmin_ind:xmax_ind]
                        ):
                            # only plot dark if it's not all zero
                            plt.plot(
                                energy_mesh[xmin_ind:xmax_ind],
                                self.jdos_dark_if[transition][xmin_ind:xmax_ind],
                                label=str(transition) + " (dark)",
                                ls="--",  # dashed linestyle for dark to distinguish
                                color=f"C{2 * i + 1}",
                            )

            else:
                list_of_curves = [
                    np.array(self.jdos_light_if[transition][xmin_ind:xmax_ind])
                    if transition in relevant_transitions
                    else None
                    for transition in self.jdos_light_if.keys()
                ]
                list_of_transitions = [
                    transition if transition in relevant_transitions else None
                    for transition in self.jdos_light_if.keys()
                ]
                list_of_curves = _rescale_overlapping_curves(list_of_curves)

                for i, transition in enumerate(list_of_transitions):
                    if transition is not None:
                        plt.plot(
                            energy_mesh[xmin_ind:xmax_ind],
                            list_of_curves[i],
                            label=str(transition) + " (light)",
                            lw=2.5,
                            color=f"C{2*i}",
                        )
                        if np.any(
                            self.jdos_dark_if[transition][xmin_ind:xmax_ind]
                        ):
                            # only plot dark if it's not all zero
                            plt.plot(
                                energy_mesh[xmin_ind:xmax_ind],
                                self.jdos_dark_if[transition][
                                    xmin_ind:xmax_ind
                                ],
                                label=str(transition) + " (dark)",
                                ls="--",  # dashed linestyle for dark to distinguish
                                color=f"C{2 * i + 1}",
                            )

        plt.ylabel(abs_label, fontsize=30)
        y_axis_min, y_axis_max = plt.gca().get_ylim()

        if ymax is None:
            ymax = y_axis_max

        if ymin is None:
            ymin = y_axis_min

        if bg is not None:
            y_bg = np.linspace(ymin, ymax)
            x_bg = np.empty(len(y_bg), dtype=float)
            x_bg.fill(bg)

            plt.plot(x_bg, y_bg, label="Bandgap", ls="--")

        if xaxis == "wavelength" and any(i is None for i in [xmax, xmin]):
            # rescale xmax so it doesn't extend to near-infinity and xmin so
            # it doesn't extend all the way to zero / negative (which is unphysical):
            lines = plt.gca().get_lines()
            max_x_for_y_gt_0 = None
            min_x_for_y_gt_0 = None

            # Iterate through lines
            for line in lines:
                xdata = line.get_xdata()
                ydata = line.get_ydata()

                # Find x values where corresponding |y| > 0.01
                x_for_y_gt_0 = xdata[np.abs(ydata) > 0.01]

                if len(x_for_y_gt_0) > 0:
                    # Find min/max x from the filtered values
                    max_x_in_line = np.max(x_for_y_gt_0)
                    min_x_in_line = np.min(x_for_y_gt_0)

                    if (
                        max_x_for_y_gt_0 is None
                        or max_x_in_line > max_x_for_y_gt_0
                    ):
                        max_x_for_y_gt_0 = max_x_in_line

                    if (
                        min_x_for_y_gt_0 is None
                        or min_x_in_line < min_x_for_y_gt_0
                    ):
                        min_x_for_y_gt_0 = min_x_in_line

            if max_x_for_y_gt_0 is not None and xmax is None:
                # Set x limit to 105% of max x-value
                xmax = max_x_for_y_gt_0 * 1.05

            if min_x_for_y_gt_0 is not None and xmin is None:
                # Set x limit to 95% of min x-value
                xmin = min_x_for_y_gt_0 * 0.95

        plt.xlim(xmin, xmax)
        plt.ylim(ymin, ymax)

        if (
            (self.material_name is not None)
            and (self.temp is not None)
            and (self.conc is not None)
        ):
            # add $_X$ around each digit X in self.material_name, to give formatted chemical formula
            formatted_material_name = re.sub(
                r"(\d)", r"$_{\1}$", self.material_name
            )
            plt.title(
                abs_label
                + " spectrum of "
                + formatted_material_name
                + " at T = "
                + str(self.temp)
                + " K, n = "
                + str(self.conc)
                + " $cm^{-3}$",
                fontsize=25,
            )

        plt.xticks(fontsize=30)
        plt.yticks(fontsize=30)
        plt.legend(
            loc=kwargs.pop("loc", "center left"),
            bbox_to_anchor=kwargs.pop("bbox_to_anchor", (1.04, 0.5)),
            fontsize=kwargs.pop("fontsize", 16),
            **kwargs,
        )

        return plt
