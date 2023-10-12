#!/usr/bin/env python3
"""
Created on Thu Aug  25 16:47:12 2023

@author: lucasverga
"""

import warnings

import numpy as np
from pymatgen.electronic_structure.core import Spin
from pymatgen.electronic_structure.dos import FermiDos, f0
from pymatgen.ext.matproj import MPRester
from pymatgen.io.vasp import optics
from pymatgen.io.vasp.inputs import UnknownPotcarWarning
from pymatgen.io.vasp.outputs import Vasprun, Waveder

import pytaser.generator as generator
from pytaser.kpoints import get_kpoint_weights

warnings.filterwarnings("ignore", category=RuntimeWarning)


class internalAs:
    """
    Class to generate an AS spectrum (decomposed and cumulative) from a bandstructure and
    dos object.

    Args:
        bs: Pymatgen-based bandstructure object
        kpoint_weights: kpoint weights either found by the function or inputted.
        dos: Pymatgen-based dos object
        dfc: Pymatgen-based DielectricFunctionCalculator object (for computing oscillator strengths)

    Attributes:
        bs: Pymatgen bandstructure object
        kpoint_weights: k-point weights (degeneracies).
        dos: Pymatgen-based dos object
        dfc: Pymatgen-based DielectricFunctionCalculator object (for computing oscillator strengths)
        bg_centre: Energy (eV) of the bandgap centre.
        vb: Spin dict detailing the valence band maxima.
        cb: Spin dict detailing the conduction band minima
    """

    def __init__(self, bs, kpoint_weights, dos, dfc=None):
        self.bs = bs
        self.kpoint_weights = kpoint_weights
        self.dos = FermiDos(dos)
        self.dfc = dfc

        if self.bs.is_metal():
            self.bg_centre = bs.efermi
            print("Is metal")
        else:
            self.bg_centre = (
                bs.get_cbm()["energy"] + bs.get_vbm()["energy"]
            ) / 2

        self.vb = generator.get_cbm_vbm_index(self.bs)[0]
        self.cb = generator.get_cbm_vbm_index(self.bs)[1]

    @classmethod
    def internal_from_vasp(cls, vasprun_file, waveder_file=None):
        """Create an internalAs object from VASP output files."""
        warnings.filterwarnings("ignore", category=UnknownPotcarWarning)
        warnings.filterwarnings(
            "ignore", message="No POTCAR file with matching TITEL fields"
        )
        vr = Vasprun(vasprun_file)

        if waveder_file:
            waveder = Waveder.from_binary(waveder_file)
            # check if LVEL was set to True in vasprun file:
            if not vr.incar.get("LVEL", False):
                lvel_error_message = (
                    "LVEL must be set to True in the INCAR for the VASP optics calculation to output the full "
                    "band-band orbital derivatives and thus allow PyTASer to parse the WAVEDER and compute oscillator "
                    "strengths. Please rerun the VASP calculation with LVEL=True (if you use the WAVECAR from the "
                    "previous calculation this should only require 1 or 2 electronic steps!"
                )
                if vr.incar.get("ISYM", 2) not in [-1, 0]:
                    isym_error_message = "ISYM must be set to 0 and "
                    raise ValueError(isym_error_message + lvel_error_message)
                else:
                    raise ValueError(lvel_error_message)
            dfc = optics.DielectricFunctionCalculator.from_vasp_objects(
                vr, waveder
            )
        else:
            dfc = None

        return cls(
            vr.get_band_structure(),
            vr.actual_kpoints_weights,
            vr.complete_dos,
            dfc,
        )

    @classmethod
    def internal_from_mpid(cls, mpid, bg=None, api_key=None, mpr=None):
        """
        Create an internalAs object from a Materials Project ID.

        Args:
            mpid: The Materials Project ID of the desired material.
            bg: The experimental bandgap (eV) of the material. If None, the band gap
                of the MP calculation will be used.
            api_key: The user's Materials Project API key.
            mpr: An MPRester object if already generated by user.

        Returns:
            internalAs object.
        """
        if mpr is None:
            if api_key is None:
                mpr = MPRester()
            else:
                mpr = MPRester(api_key=api_key)
        mp_dos = mpr.get_dos_by_material_id(mpid)
        mp_bs = mpr.get_bandstructure_by_material_id(mpid, line_mode=False)
        if bg is not None:
            mp_bs, mp_dos = generator.set_bandgap(mp_bs, mp_dos, bg)
        kweights = get_kpoint_weights(mp_bs)

        return cls(mp_bs, kweights, mp_dos, None)

    def band_occupancies(self, temp):
        """
        Gives band occupancies.

        Returns:
            A dictionary of {Spin: occ} for all bands across all k-points.
        """
        occs = {}
        for spin, spin_bands in self.bs.bands.items():
            hole_mask = spin_bands < self.bg_centre
            elec_mask = spin_bands > self.bg_centre
            # fully occupied hole mask, completely empty electron mask
            spin_occs = np.zeros_like(spin_bands)
            if self.bs.is_metal():
                spin_occs[hole_mask] = f0(spin_bands, self.bg_centre, temp)[
                    hole_mask
                ]
                spin_occs[elec_mask] = f0(spin_bands, self.bg_centre, temp)[
                    elec_mask
                ]
            else:
                spin_occs[hole_mask] = 1
                spin_occs[elec_mask] = 0

            occs[spin] = spin_occs

        return occs

    def generate_As(
        self,
        temp,
        energy_min=0,
        energy_max=5,
        gaussian_width=0.1,
        cshift=None,
        step=0.01,
        occs=None,
        processes=None,
    ):
        """
        Generates AS spectra based on inputted occupancies, and a specified energy mesh.

        Args:
            temp: Temperature (K) of material we wish to investigate (affects the FD distribution)
            energy_min: Minimum band transition energy to consider for energy mesh (eV)
            energy_max: Maximum band transition energy to consider for energy mesh (eV)
            gaussian_width: Width of gaussian curve
            cshift: Complex shift in the Kramers-Kronig transformation of the dielectric function
                (see https://www.vasp.at/wiki/index.php/CSHIFT). If not set, uses the value of
                CSHIFT from the underlying VASP WAVEDER calculation. (only relevant if the
                DASGenerator has been generated from VASP outputs)
            step: Interval between energy points in the energy mesh.
            occs: Optional input parameter for occupancies of material, otherwise
                automatically calculated based on input temperature (temp)
            processes: Number of processes to use for multiprocessing. If not set, defaults to one
                less than the number of CPUs available.

        Returns:
                - jdos_dark_total: overall JDOS for a material under the
                    specified conditions
                - jdos_dark_if: JDOS  across the energy mesh for a specific band
                    transition i (initial) -> f (final) [dict]
                - alpha_dark: Absorption coefficient of the material, in cm^-1 (only
                    calculated if the DASGenerator has been generated from VASP outputs)
                - weighted_jdos_dark_if: JDOS across the energy mesh for a specific band
                    transition i (initial) -> f (final), weighted by the oscillator strength of
                    the transition [dict]
        """
        occs = occs
        if occs is None:
            occs = self.band_occupancies(temp)

        energy_mesh_ev = np.arange(energy_min, energy_max, step)
        jdos_dark_if = {}
        weighted_jdos_dark_if = {}
        jdos_dark_total = np.zeros(len(energy_mesh_ev))

        if self.dfc is not None:
            egrid = np.linspace(
                0,
                self.dfc.nedos * self.dfc.deltae,
                self.dfc.nedos,
                endpoint=False,
            )

            alpha_dark = np.zeros_like(egrid, dtype=np.complex128)

        for spin, spin_bands in self.bs.bands.items():
            if self.dfc is not None:
                alpha_dark_dict, tdm_array = generator.occ_dependent_alpha(
                    self.dfc,
                    occs[spin],
                    sigma=gaussian_width,
                    cshift=cshift,
                    processes=processes,
                    energy_max=energy_max,
                )
                alpha_dark += alpha_dark_dict[
                    "both"
                ]  # stimulated emission should be
                # zero in the dark

            for i in range(len(spin_bands)):
                for f in range(len(spin_bands)):
                    if f > i:
                        jd_dark = generator.jdos(
                            self.bs,
                            f,
                            i,
                            occs[spin],
                            energy_mesh_ev,
                            self.kpoint_weights,
                            gaussian_width,
                            spin=spin,
                        )
                        jdos_dark_total += jd_dark

                        new_i = i - self.vb[spin]
                        new_f = f - self.vb[spin]

                        if self.bs.is_spin_polarized:
                            spin_str = "up" if spin == Spin.up else "down"
                            key = (new_i, new_f, spin_str)
                        else:
                            key = (new_i, new_f)

                        jdos_dark_if[key] = jd_dark

                        if self.dfc is not None:
                            weighted_jd_dark = generator.jdos(
                                self.bs,
                                f,
                                i,
                                occs[spin],
                                energy_mesh_ev,
                                np.array(self.kpoint_weights)
                                * tdm_array[i, f, :],
                                gaussian_width,
                                spin=spin,
                            )

                            weighted_jdos_dark_if[key] = weighted_jd_dark

        # need to interpolate alpha arrays onto JDOS energy mesh:
        if self.dfc is not None:
            alpha_dark = np.interp(energy_mesh_ev, egrid, alpha_dark)

        return (
            jdos_dark_total,
            jdos_dark_if,
            alpha_dark if self.dfc is not None else None,
            weighted_jdos_dark_if if self.dfc is not None else None,
        )
