import re
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import scipy.constants as scpc


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
        container: TAS container class as generated by tas.
        bandgap_ev: The experimental bandgap of the material (eV) [leave blank if generated by
            from mpid)
        material_name: Name of material being investigated (string) [optional, for labelling]
        temp: Temperature of TAS spectrum. Note that this _does not_ recalculate the TAS/JDOS
            spectra and is only for labelling; if you want to recalculate the spectra you should
            change `temp` in the `generate_tas()` function! [optional, for labelling]
        conc: Number of charge carriers (#electrons = #holes, assumes no recombination). Note
            that this _does not_ recalculate the TAS/JDOS spectra and is only for labelling; if
            you want to recalculate the spectra you should change `conc` in the `generate_tas()`
            function! [optional, for labelling]
    """

    def __init__(
        self,
        container,
        bandgap_ev=None,
        material_name=None,
        temp=None,
        conc=None,
    ):
        self.tas_tot = container.total_tas
        self.tas_decomp = container.tas_decomp
        self.jdos_light_tot = container.jdos_light_tot
        self.jdos_light_decomp = container.jdos_light_decomp
        self.jdos_dark_tot = container.jdos_dark_tot
        self.jdos_dark_decomp = container.jdos_dark_decomp
        self.energy_mesh_ev = container.energy_mesh_ev
        if bandgap_ev is None:
            self.bandgap_ev = container.bandgap
        elif bandgap_ev is not None:
            self.bandgap_ev = bandgap_ev
        self.material_name = material_name
        self.temp = temp
        self.conc = conc
        self.energy_mesh_lambda = ev_to_lambda(self.energy_mesh_ev)
        self.bandgap_lambda = ev_to_lambda(self.bandgap_ev)

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
    ):
        """
        Args:
            relevant_transitions: List containing individual transitions to be displayed
                in the plot alongside the total plot. If material is not spin-polarised,
                only write the bands involved [(-1,6),(2,7),(-8,-5)...] If spin-polarised,
                include the type of spin involved in transition
                [(-1,6, "down"),(2,7, "down"),(-8,-5, "up")...]
                Default is 'auto' mode, which shows all band transitions above the transition_cutoff.
            xaxis: Units for the energy mesh. Either in wavelengths or energy.
            transition_cutoff: The minimum height of the band transition as a percentage threshold of the most
                contributing transition (Across all kpoints, within the energy range specified). Default is 3%.
            xmin: Minimum energy point in mesh (float64)
            xmax: Maximum energy point in mesh (float64)
            ymin: Minimum absorption point. Default is 1.15 * minimum point.
            ymax: Maximum absorption point. Default is 1.15 * maximum point.
            yaxis: Measurement method of absorption (jdos or tas) (string)

        Returns:
            Matplotlib pyplot of the desired spectrum, with labelled units.
        """
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
            bg = self.bandgap_ev
            plt.xlabel("Energy (eV)", fontsize=30)

        if xmin is not None:
            if xmin < np.min(energy_mesh):
                raise ValueError(
                    "Plotting region xmin value is smaller than energy mesh minimum. Please specify in "
                    "same units as xaxis"
                )
            if xmin > np.max(energy_mesh):
                raise ValueError(
                    "Plotting region xmin value is larger than energy mesh maximum. Please specify in "
                    "same units as xaxis"
                )

        if xmax is not None:
            if xmax < np.min(energy_mesh):
                raise ValueError(
                    "Plotting region xmax value is smaller than energy mesh minimum. Please specify in "
                    "same units as xaxis"
                )
            if xmax > np.max(energy_mesh):
                raise ValueError(
                    "Plotting region xmax value is larger than energy mesh maximum. Please specify in "
                    "same units as xaxis"
                )

        abs_label = ""

        if yaxis == "tas":
            abs_label = "ΔT (a.u.)"

            plt.plot(
                energy_mesh[xmin_ind:xmax_ind],
                self.tas_tot[xmin_ind:xmax_ind],
                label="total TAS",
                color="black",
                lw=3.5,
            )

            if relevant_transitions == "auto":
                relevant_transition_list = cutoff_transitions(
                    self.tas_decomp, transition_cutoff, xmin_ind, xmax_ind
                )

                # group transitions with (almost) equal energies:
                groups = defaultdict(list)
                for index, transition in enumerate(relevant_transition_list):
                    if transition is not None:
                        tas_curve = self.tas_decomp[transition][xmin_ind:xmax_ind]
                        tas_area = np.trapz(tas_curve, energy_mesh[xmin_ind:xmax_ind])
                        # group by position of max point and area under curve (to account for
                        # possibility of degeneracy at max point, but not for the full curve (if
                        # e.g. two bands are degenerate at a single kpoint but not across the BZ)
                        groups[f"{np.argmax(np.abs(tas_curve))}, {tas_area:.2f}"].append(
                            (transition, tas_curve, index)
                        )

                for coords, transition_tuple_list in groups.items():
                    transition_tuple_array = np.array(transition_tuple_list, dtype=object)
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        sum(transition_tuple_array[:, 1]),
                        label=", ".join([str(transition) for transition
                                         in transition_tuple_array[:, 0]]
                                        ),
                        lw=2.5,
                        color=f"C{transition_tuple_array[0, 2]}"
                    )

            else:
                for transition in relevant_transitions:
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        self.tas_decomp[transition][xmin_ind:xmax_ind],
                        label=transition,
                        lw=2.5
                    )

        elif yaxis == "jdos":
            abs_label = "JDOS (a.u.)"
            plt.plot(
                energy_mesh[xmin_ind:xmax_ind],
                self.jdos_light_tot[xmin_ind:xmax_ind],
                label="JDOS (light)",
                color="black",
                lw=2.5,
            )
            plt.plot(
                energy_mesh[xmin_ind:xmax_ind],
                self.jdos_dark_tot[xmin_ind:xmax_ind],
                label="JDOS (dark)",
                color="blue",
                lw=2.5,
            )

            if relevant_transitions == "auto":
                relevant_transition_list = cutoff_transitions(
                    self.jdos_light_decomp,
                    transition_cutoff,
                    xmin_ind,
                    xmax_ind,
                )

                # group transitions with (almost) equal energies:
                groups = defaultdict(list)
                for index, transition in enumerate(relevant_transition_list):
                    if transition is not None:
                        jdos_light_curve = self.jdos_light_decomp[transition][xmin_ind:xmax_ind]
                        jdos_dark_curve = self.jdos_dark_decomp[transition][xmin_ind:xmax_ind]
                        jdos_light_area = np.trapz(jdos_light_curve, energy_mesh[xmin_ind:xmax_ind])
                        # group by position of max point and area under curve (to account for
                        # possibility of degeneracy at max point, but not for the full curve (if
                        # e.g. two bands are degenerate at a single kpoint but not across the BZ)
                        groups[f"{np.argmax(np.abs(jdos_light_curve))}," \
                               f" {jdos_light_area:.2f}"].append(
                            (transition, jdos_light_curve, jdos_dark_curve, index)
                        )

                for coords, transition_tuple_list in groups.items():
                    transition_tuple_array = np.array(transition_tuple_list, dtype=object)
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        sum(transition_tuple_array[:, 1]),
                        label=", ".join([str(transition) for transition
                                         in transition_tuple_array[:, 0]]
                                        ) + " (light)",
                        color=f"C{2*transition_tuple_array[0, 3]}"
                    )
                    if np.any(sum(transition_tuple_array[:, 2])):
                        # only plot dark if it's not all zero
                        plt.plot(
                            energy_mesh[xmin_ind:xmax_ind],
                            sum(transition_tuple_array[:, 2]),
                            label=", ".join([str(transition) for transition
                                             in transition_tuple_array[:, 0]]
                                            ) + " (dark)",
                            ls="--",  # dashed linestyle for dark to distinguish
                            alpha=0.5,  # make semi-transparent to show if overlapping lines
                            color=f"C{2 * transition_tuple_array[0, 3] + 1}"
                        )

            else:
                for transition in relevant_transitions:
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        self.jdos_light_decomp[transition][xmin_ind:xmax_ind],
                        label=str(transition) + " (light)",
                    )
                    if np.any(self.jdos_dark_decomp[transition][
                                xmin_ind:xmax_ind
                            ]):
                        # only plot dark if it's not all zero
                        plt.plot(
                            energy_mesh[xmin_ind:xmax_ind],
                            self.jdos_dark_decomp[transition][xmin_ind:xmax_ind],
                            label=str(transition) + " (dark)",
                            ls="--",  # dashed linestyle for dark to distinguish
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

        plt.xlim(xmin, xmax)
        plt.ylim(ymin, ymax)

        if (
            (self.material_name is not None)
            and (self.temp is not None)
            and (self.conc is not None)
        ):
            # add $_X$ around each digit X in self.material_name, to give formatted chemical formula
            formatted_material_name = re.sub(r"(\d)", r"$_{\1}$", self.material_name)
            plt.title(
                abs_label
                + " spectrum of "
                + formatted_material_name
                + " at T = "
                + str(self.temp)
                + " K, n = "
                + str(self.conc)
                + " $cm^{-3}$",
                fontsize=25
            )

        plt.xticks(fontsize=30)
        plt.yticks(fontsize=30)
        plt.legend(loc="center left", bbox_to_anchor=(1.04, 0.5),fontsize=16)

        return plt
