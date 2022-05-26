import matplotlib.pyplot as plt
import numpy as np
import scipy.constants as scpc


def ev_to_lambda(ev):
    """Convert photon energies from eV to a wavelength in nm."""
    wavelength = ((scpc.h * scpc.c) / (ev * scpc.electron_volt)) * 10e8
    return wavelength


def lambda_to_ev(lambda_float):
    """Convert photon energies from a wavelength in nm to eV."""
    electronvolts = (10e8 * (scpc.h * scpc.c)) / (lambda_float * scpc.electron_volt)
    return electronvolts


class TASPlotter:
    """
    Class to generate a matplotlib plot of the TAS or JDOS spectra, with a specific energy
    mesh, material, and conditions.'

    Args:
        container: TAS container class as generated by tas.
        bandgap_ev: The experimental bandgap of the material (eV) [leave blank if generated by from_mpid)
        material_name: Name of material being investigated (string) [optional, for labelling]
        temp: Temperature of TAS spectrum. [optional, for labelling]
        conc: Number of charge carriers (#electrons = #holes, assumes no recombination) [optional, for labelling]
    """

    def __init__(
            self, container, bandgap_ev=None, material_name=None, temp=None, conc=None
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
            yaxis="TAS (deltaT)",
    ):
        """
        Args:
            relevant_transitions: List containing individual transitions to be displayed
                in the plot alongside the total plot. If material is not spin-polarised,
                only write the bands involved [(-1,6),(2,7),(-8,-5)...] If spin-polarised,
                include the type of spin involved in transition
                [(-1,6, "down"),(2,7, "down"),(-8,-5, "up")...]
                Default is 'auto' mode, which shows the band transitions with the 3 highest
                absorption values (overall across all k-points).
            xaxis: Units for the energy mesh. Either in wavelengths or energy.
            transition_cutoff: The minimum height of the band transition as a percentage threshold compared to the most
                contributing transition. Default is set at 3%.
            xmin: Minimum energy point in mesh (float64)
            xmax: Maximum energy point in mesh (float64)
            ymin: Minimum absorption point. Default is 1.15 * minimum point.
            ymax: Maximum absorption point. Default is 1.15 * maximum point.
            yaxis: Measurement method of absorption (JDOS or deltaT) (string)

        Returns:
            Matplotlib pyplot of the desired spectrum, with labelled units.
        """
        energy_mesh = 0
        bg = 0
        plt.figure(figsize=(8, 5))

        xmin_ind = 0
        xmax_ind = -1

        if xaxis == "wavelength":
            energy_mesh = self.energy_mesh_lambda
            if xmin is not None:
                xmax_ind = np.abs(energy_mesh - xmin).argmin()
            if xmax is not None:
                xmin_ind = np.abs(energy_mesh - xmax).argmin()
            bg = self.bandgap_lambda
            plt.xlabel("Wavelength (nm)")

        elif xaxis == "energy":
            energy_mesh = self.energy_mesh_ev
            if xmin is not None:
                xmin_ind = np.abs(energy_mesh - xmin).argmin()
            if xmax is not None:
                xmax_ind = np.abs(energy_mesh - xmax).argmin()
            bg = self.bandgap_ev
            plt.xlabel("Energy (eV)")

        if xmin is not None:
            if (xmin < np.min(energy_mesh)):
                raise ValueError("Plotting region xmin value is smaller than energy mesh minimum. Please specify in "
                                 "same units as xaxis")
            if (xmin > np.max(energy_mesh)):
                raise ValueError("Plotting region xmin value is larger than energy mesh maximum. Please specify in "
                                 "same units as xaxis")

        if xmax is not None:
            if (xmax < np.min(energy_mesh)):
                raise ValueError("Plotting region xmax value is smaller than energy mesh minimum. Please specify in "
                                 "same units as xaxis")
            if (xmax > np.max(energy_mesh)):
                raise ValueError("Plotting region xmax value is larger than energy mesh maximum. Please specify in "
                                 "same units as xaxis")

        abs_label = ""

        if yaxis == "TAS (deltaT)":
            abs_label = "ΔT (a.u.)"

            plt.plot(
                energy_mesh[xmin_ind:xmax_ind], self.tas_tot[xmin_ind:xmax_ind], label="total TAS", color="black",
                lw=2.5
            )

            if relevant_transitions == "auto":

                max_abs_vals = {key: np.max(abs(val[xmin_ind:xmax_ind])) for key, val in self.tas_decomp.items()}
                max_val = max(max_abs_vals.values())
                for transition, value in max_abs_vals.items():
                    if value >= (max_val * transition_cutoff):
                        plt.plot(energy_mesh[xmin_ind:xmax_ind], self.tas_decomp[transition][xmin_ind:xmax_ind],
                                 label=transition)

            else:
                for transition in relevant_transitions:
                    plt.plot(energy_mesh[xmin_ind:xmax_ind], self.tas_decomp[transition][xmin_ind:xmax_ind],
                             label=transition)

        elif yaxis == "JDOS":
            abs_label = "JDOS (a.u.)"
            plt.plot(
                energy_mesh[xmin_ind:xmax_ind],
                self.jdos_light_tot[xmin_ind:xmax_ind],
                label="JDOS (light)",
                color="black",
                lw=1.5,
            )
            plt.plot(
                energy_mesh[xmin_ind:xmax_ind],
                self.jdos_dark_tot[xmin_ind:xmax_ind],
                label="JDOS (dark)",
                color="blue",
                lw=1.5,
            )

            if relevant_transitions == "auto":

                max_abs_vals_jd_light = {key: np.max(abs(val[xmin_ind:xmax_ind])) for key, val in
                                         self.jdos_light_decomp.items()}
                max_val_jd_light = max(max_abs_vals_jd_light.values())
                for transition_jd, value_jd in max_abs_vals_jd_light.items():
                    if value_jd >= (max_val_jd_light * transition_cutoff):
                        plt.plot(energy_mesh[xmin_ind:xmax_ind],
                                 self.jdos_light_decomp[transition_jd][xmin_ind:xmax_ind],
                                 label=str(transition_jd) + "(light)")
                        plt.plot(energy_mesh[xmin_ind:xmax_ind],
                                 self.jdos_dark_decomp[transition_jd][xmin_ind:xmax_ind],
                                 label=str(transition_jd) + "(dark)")

            else:
                for transition in relevant_transitions:
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        self.jdos_light_decomp[transition][xmin_ind:xmax_ind],
                        label=str(transition) + " (light)",
                    )
                    plt.plot(
                        energy_mesh[xmin_ind:xmax_ind],
                        self.jdos_dark_decomp[transition][xmin_ind:xmax_ind],
                        label=str(transition) + " (dark)",
                    )

        plt.ylabel(abs_label)
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

        if (self.material_name != None) and (self.temp != None) and (self.conc != None):
            plt.title(
                abs_label
                + " spectrum of "
                + self.material_name
                + " at T = "
                + str(self.temp)
                + " K, n = "
                + str(self.conc)
            )

        plt.legend(loc="best")

        return plt
