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
        bandgap_ev: The experimental bandgap of the material to be implemented (eV)
        material_name: Name of material being investigated (string)
        temp: Temperature of TAS spectrum. Will affect occupancy according to FD
            distribution (K)
        conc: Number of charge carriers (#electrons = #holes, assumes no recombination)
    """

    def __init__(self, container, bandgap_ev, material_name, temp, conc):
        self.tas_tot = container.total_tas
        # self.denom_tas_tot = container.denom_total_TAS
        self.tas_decomp = container.tas_decomp
        # self.denom_tas_decomp = container.denom_TAS_decomp
        self.jdos_light_tot = container.jdos_light_tot
        self.jdos_light_decomp = container.jdos_light_decomp
        self.jdos_dark_tot = container.jdos_dark_tot
        self.jdos_dark_decomp = container.jdos_dark_decomp
        self.energy_mesh_ev = container.energy_mesh_ev
        self.bandgap_ev = bandgap_ev
        self.material_name = material_name
        self.temp = temp
        self.conc = conc
        self.bandgap_lambda = ev_to_lambda(self.bandgap_ev)
        self.energy_mesh_lambda = ev_to_lambda(self.energy_mesh_ev)

    def get_plot(
        self,
        relevant_transitions=None,
        xaxis="wavelength",
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
                only write the bands involved [(1,6),(2,7),(8,9)...] If spin-polarised,
                include the type of spin involved in transition
                [(1,6, "down"),(2,7, "down"),(8,9, "up")...]
            xaxis: Units for the energy mesh. Either in wavelengths or electronvolts.
            xmin: Minimum energy point in mesh (float)
            xmax: Maximum energy point in mesh (float)
            ymin: Minimum absorption point. Default is 1.15 * minimum point.
            ymax: Maximum absorption point. Default is 1.15 * maximum point.
            yaxis: Measurement method of absorption (JDOS or deltaT) (string)
                [deltaT/T is currently being worked on.]

        Returns:
            Matplotlib pyplot of the desired spectrum, with labelled units.
        """
        energy_mesh = 0
        bg = 0
        plt.figure(figsize=(15, 10))
        if xaxis == "wavelength":
            energy_mesh = self.energy_mesh_lambda
            bg = self.bandgap_lambda
            plt.xlabel("Wavelengths (nm)")

        elif xaxis == "electronvolts":
            energy_mesh = self.energy_mesh_ev
            bg = self.bandgap_ev
            plt.xlabel("Energy (eV)")

        # plt.plot(energy_mesh, self.tas_tot, label='total TAS', color='black', lw=2.5)

        # if relevant_transitions is None:
        #     pass
        # else:
        #     for transition in relevant_transitions:
        #         plt.plot(energy_mesh, self.tas_decomp[transition], label=transition)

        y_axis_max = 0.15
        y_axis_min = -0.15
        abs_label = ""
        if yaxis == "TAS (deltaT)":
            abs_label = "ΔT (a.u.)"

            plt.plot(
                energy_mesh, self.tas_tot, label="total TAS", color="black", lw=2.5
            )

            y_axis_max = 1.15 * max(self.tas_tot)
            y_axis_min = 1.15 * min(self.tas_tot)

            if relevant_transitions is not None:
                for transition in relevant_transitions:
                    plt.plot(energy_mesh, self.tas_decomp[transition], label=transition)

        ######### deltaT/T IS CURRENTLY NON-FUNCTIONING - we encounter a 'divide by `zero error' ###########
        # elif yaxis == "TAS (deltaT/T)":
        #     abs_label = 'ΔT/T (a.u.)'
        # #   the denominator refers to JDOS light.
        #     plt.plot(energy_mesh, self.denom_tas_tot, label='total TAS', color='black', lw=2.5)
        #
        #     y_axis_max = 1.15 * max(self.denom_tas_tot)
        #     y_axis_min = 1.15 * min(self.denom_tas_tot)
        #
        #     if relevant_transitions is not None:
        #         for transition in relevant_transitions:
        #             plt.plot(energy_mesh, self.denom_tas_decomp[transition], label=transition)

        elif yaxis == "JDOS":
            abs_label = "JDOS (a.u.)"
            y_axis_max = 1.15 * max(self.jdos_light_tot)
            y_axis_min = 1.15 * min(self.jdos_light_tot)
            plt.plot(
                energy_mesh,
                self.jdos_light_tot,
                label="JDOS (light)",
                color="black",
                lw=1.5,
            )
            plt.plot(
                energy_mesh,
                self.jdos_dark_tot,
                label="JDOS (dark)",
                color="blue",
                lw=1.5,
            )

            if relevant_transitions is not None:
                for transition in relevant_transitions:
                    plt.plot(
                        energy_mesh,
                        self.jdos_light_decomp[transition],
                        label=str(transition) + " (light)",
                    )
                    plt.plot(
                        energy_mesh,
                        self.jdos_dark_decomp[transition],
                        label=str(transition) + " (dark)",
                    )

        plt.ylabel(abs_label)

        if ymax is None:
            ymax = y_axis_max

        if ymin is None:
            ymin = y_axis_min

        # bg = 0
        # if xaxis == "wavelength":
        #     plt.xlabel('Wavelengths (nm)')
        #     bg += ev_to_lambda(self.bandgap_ev)
        #
        # elif xaxis == "electronvolts":
        #     plt.xlabel('Energy (eV)')
        #     bg += self.bandgap_ev

        y_bg = np.linspace(ymin, ymax)
        x_bg = np.empty(len(y_bg), dtype=float)
        x_bg.fill(bg)

        plt.plot(x_bg, y_bg, label="Bandgap", ls="--")

        plt.xlim(xmin, xmax)
        plt.ylim(ymin, ymax)

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
