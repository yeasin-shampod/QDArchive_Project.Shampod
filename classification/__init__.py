"""Part 2: Data Classification package for QDArchive seeding.

This package implements the Part 2 requirements:

1. PROJECT_TYPE classification (QDA_PROJECT, QD_PROJECT, OTHER_PROJECT,
   NOT_A_PROJECT) derived from the file extensions present in a project.
2. A hierarchical ISIC Rev. 5 classifier (section + division, i.e. two levels)
   that classifies both whole projects and their individual primary data files.
3. Helpers that the export modules use to produce the XLSX table and the PDF
   report required by the assignment.
"""
