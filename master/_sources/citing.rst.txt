Citing NL-BIOMERO and BIOMERO
==============================

Thank you for citing the work that made NL-BIOMERO and BIOMERO possible.
The appropriate paper depends on which part of the ecosystem your work uses.

Which paper should I cite?
--------------------------

* **NL-BIOMERO, BIOMERO 2.0, or the complete platform:** cite the 2026
  *Journal of Microscopy* paper. This paper describes the end-to-end
  infrastructure, including data import and preprocessing with
  BIOMERO.importer, analysis, provenance, and the integrated OMERO experience.
* **The BIOMERO Python library or HPC analysis framework:** cite the 2024
  *Patterns* paper. This paper describes the scalable workflow-execution
  framework connecting OMERO, FAIR workflows, and Slurm/HPC resources.
* **Work that relies substantially on both layers:** citing both papers gives
  readers the clearest account of the complete system and its core analysis
  framework.

BIOMERO 2.0 / NL-BIOMERO
------------------------

Luik, T. T., de Folter, J., Rosas-Bertolini, R., Reits, E. A. J., Hoebe,
R. A., & Krawczyk, P. M. (2026). BIOMERO 2.0: End-to-end FAIR infrastructure
for bioimaging data import, analysis, and provenance. *Journal of Microscopy*.
`https://doi.org/10.1111/jmi.70114 <https://doi.org/10.1111/jmi.70114>`_

.. code-block:: bibtex

   @article{Luik2026BIOMERO2,
     author  = {Luik, Torec T. and de Folter, Joost and Rosas-Bertolini, Rodrigo and Reits, Eric A. J. and Hoebe, Ron A. and Krawczyk, Przemek M.},
     title   = {BIOMERO 2.0: End-to-end FAIR infrastructure for bioimaging data import, analysis, and provenance},
     journal = {Journal of Microscopy},
     year    = {2026},
     doi     = {10.1111/jmi.70114},
     url     = {https://doi.org/10.1111/jmi.70114}
   }

BIOMERO analysis framework
--------------------------

Luik, T. T., Rosas-Bertolini, R., Reits, E. A. J., Hoebe, R. A., & Krawczyk,
P. M. (2024). BIOMERO: A scalable and extensible image analysis framework.
*Patterns, 5*\ (8), 101024.
`https://doi.org/10.1016/j.patter.2024.101024 <https://doi.org/10.1016/j.patter.2024.101024>`_

.. code-block:: bibtex

   @article{Luik2024BIOMERO,
     author  = {Luik, Torec T. and Rosas-Bertolini, Rodrigo and Reits, Eric A. J. and Hoebe, Ron A. and Krawczyk, Przemek M.},
     title   = {BIOMERO: A scalable and extensible image analysis framework},
     journal = {Patterns},
     volume  = {5},
     number  = {8},
     pages   = {101024},
     year    = {2024},
     doi     = {10.1016/j.patter.2024.101024},
     url     = {https://doi.org/10.1016/j.patter.2024.101024}
   }

Software citation metadata
--------------------------

The repository also provides machine-readable citation metadata in
`CITATION.cff <https://github.com/NL-BioImaging/NL-BIOMERO/blob/master/CITATION.cff>`_.
Please report the NL-BIOMERO version and the relevant workflow and container
versions in methods and data-provenance records.
