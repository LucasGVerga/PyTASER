#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug  3 16:42:36 2023

@author: lucasverga
"""

import warnings
import numpy as np
from pymatgen.io.vasp.inputs import UnknownPotcarWarning
from pytaser.tas import Das
import pytaser.createinternalDas as createinternalDas

warnings.filterwarnings("ignore", category=RuntimeWarning)


class DASGenerator:
    """
    Class to generate a DAS spectrum (decomposed and cumulative) from a bandstructure and
    dos object.

    Args:
        newSystem: internalAs object from createinternalDas module for the new system
        referenceSystem: internalAs object from createinternalDas module for the reference system
    Attributes:
        newSystem: internalAs object from createinternalDas module for the new system
        referenceSystem: internalAs object from createinternalDas module for the reference system
    """

    def __init__(
        self,
        newSystem,
        referenceSystem,
    ):
        self.newSystem = newSystem
        self.referenceSystem = referenceSystem

    @classmethod
    def from_vasp_outputs(
        cls,
        vasprun_file_newSystem,
        vasprun_file_ref,
        waveder_file_newSystem=None,
        waveder_file_ref=None,
    ):
        """
        Create a DASGenerator object from VASP output files.

        The user should provide the vasprun files for the new system and the reference system,
        followed by the waveder files for the new system and the reference system.

        Args:
            vasprun_file_newSystem: The vasprun.xml file for the new system.
            vasprun_file_ref: The vasprun.xml file for the reference system.
            waveder_file_newSystem: The WAVEDER file for the new system.
            waveder_file_ref: The WAVEDER file for the reference system.
        Returns:
            A DASGenerator object containing the internalAs object for the new system and reference system.
        """
        warnings.filterwarnings("ignore", category=UnknownPotcarWarning)
        warnings.filterwarnings(
            "ignore", message="No POTCAR file with matching TITEL fields"
        )

        newSystem = createinternalDas.internalAs.internal_from_vasp(
            vasprun_file_newSystem, waveder_file_newSystem
        )
        referenceSystem = createinternalDas.internalAs.internal_from_vasp(
            vasprun_file_ref, waveder_file_ref
        )

        return cls(newSystem, referenceSystem)

    @classmethod
    def from_mpid(
        cls,
        mpid,
        mpid_ref,
        bg=None,
        bg_ref=None,
        api_key=None,
        mpr=None,
        mpr_ref=None,
    ):
        """
        Import the desired bandstructure and dos objects from the legacy Materials Project
        database.

        Args:
            mpid: The Materials Project ID of the new system.
            mpid_ref: The Materials Project ID of the reference system.
            bg: The experimental bandgap (eV) of the new system. If None, the band gap
                of the MP calculation will be used.
            bg_ref: The experimental bandgap (eV) of the reference system. If None, the band gap
                of the MP calculation will be used.
            api_key: The user's Materials Project API key.
            mpr: An MPRester object for the new system if already generated by user.
            mpr_ref: An MPRester object for the reference system if already generated by user.

        Returns:
            A DASGenerator object containing the internalAs object for the new system and reference system.
        """
        newSystem = createinternalDas.internalAs.internal_from_mpid(
            mpid, bg=None, api_key=None, mpr=None
        )
        referenceSystem = createinternalDas.internalAs.internal_from_mpid(
            mpid_ref, bg_ref, api_key=None, mpr_ref=None
        )

        return cls(newSystem, referenceSystem)

    def generate_das(
        self,
        temp,
        energy_min=0,
        energy_max=5,
        gaussian_width=0.1,
        cshift=None,
        step=0.01,
        newSys_occs=None,
        ref_occs=None,
        processes=None,
    ):
        """
        Generates DAS spectra (new system - reference system) based on inputted occupancies,
        and a specified energy mesh. If the DASGenerator has not been generated from VASP
        outputs (and thus does not have a dfc attribute), then the output DAS is generated
        using the change in joint density of states (JDOS) from both systems, with no consideration
        of oscillator strengths. Otherwise, the output DAS is generated considering all contributions
        to the predicted DAS spectrum.

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
            newSys_occs: Optional input parameter for occupancies of the new system, otherwise
                automatically calculated based on input temperature (temp)
            reference_occs: Optional input parameter for occupancies of the reference system, otherwise
                automatically calculated based on input temperature (temp)
            processes: Number of processes to use for multiprocessing. If not set, defaults to one
                less than the number of CPUs available.

        Returns:
            DAS class containing the following inputs;
                - das_total: overall deltaT DAS spectrum for new system - reference system.
                - jdos_newSys_total: overall JDOS for the new system.
                - jdos_newSys_if: JDOS for the new system across the energy mesh for a specific band
                    transition i (initial) -> f (final) [dict]
                - jdos_ref_total: overall JDOS for the reference system.
                - jdos_ref_if: JDOS for the reference system across the energy mesh for a specific band
                    transition i (initial) -> f (final) [dict]
                - energy_mesh_ev: Energy mesh of spectra in eV, with an interval of 'step'.
                - bandgap: Bandgap of the system, in eV, rounded to 2 decimal points
                - temp: Temperature of the system, in K
                - alpha_ref: Absorption coefficient of the reference system, in cm^-1 (only
                    calculated if the DASGenerator has been generated from VASP outputs)
                - alpha_newSys: Absorption coefficient of the new system, in cm^-1 (only
                    calculated if the DASGenerator has been generated from VASP outputs
                - weighted_jdos_diff_if: JDOS difference (from reference to new system) across the energy
                    mesh for a specific band transition i (initial) -> f (final), weighted by the
                    oscillator strength of the transition [dict]
                - weighted_jdos_newSys_if: JDOS of new system across the energy mesh for a specific band
                    transition i (initial) -> f (final), weighted by the oscillator strength of
                    the transition [dict]
        """
        bandgap_ref = round(
            self.referenceSystem.bs.get_band_gap()["energy"], 2
        )
        bandgap_newSys = round(self.newSystem.bs.get_band_gap()["energy"], 2)

        energy_mesh_ev = np.arange(energy_min, energy_max, step)

        (
            jdos_ref_total,
            jdos_ref_if,
            alpha_ref,
            weighted_jdos_ref_if,
        ) = createinternalDas.internalAs.generate_As(
            self.referenceSystem,
            temp,
            energy_min,
            energy_max,
            gaussian_width,
            cshift,
            step,
            ref_occs,
            processes,
        )

        (
            jdos_newSys_total,
            jdos_newSys_if,
            alpha_newSys,
            weighted_jdos_newSys_if,
        ) = createinternalDas.internalAs.generate_As(
            self.newSystem,
            temp,
            energy_min,
            energy_max,
            gaussian_width,
            cshift,
            step,
            newSys_occs,
            processes,
        )

        das_total = jdos_newSys_total - jdos_ref_total
        # need to interpolate alpha arrays onto JDOS energy mesh:
        if self.referenceSystem.dfc and self.newSystem.dfc is not None:
            das_total = alpha_newSys - alpha_ref

        return Das(
            das_total,
            jdos_newSys_total,
            jdos_newSys_if,
            jdos_ref_total,
            jdos_ref_if,
            energy_mesh_ev,
            bandgap_newSys,
            bandgap_ref,
            temp,
            alpha_newSys if self.newSystem.dfc is not None else None,
            alpha_ref if self.referenceSystem.dfc is not None else None,
            weighted_jdos_newSys_if
            if self.newSystem.dfc is not None
            else None,
            weighted_jdos_ref_if
            if self.referenceSystem.dfc is not None
            else None,
        )
