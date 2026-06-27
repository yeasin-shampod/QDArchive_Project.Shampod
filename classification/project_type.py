"""Derive the PROJECT_TYPE of a research project from its files.

Decision rule (assignment, Part 2 Step 1 continued):

* ``QDA_PROJECT``    -- there is at least one file with a QDA file extension.
* ``QD_PROJECT``     -- not a QDA_PROJECT, but there are primary data files.
* ``OTHER_PROJECT``  -- not a QD_PROJECT, but there are other valid data files.
* ``NOT_A_PROJECT``  -- nothing can be derived about the file types.
"""

from classification.file_types import file_role

PROJECT_TYPES = ("QDA_PROJECT", "QD_PROJECT", "OTHER_PROJECT", "NOT_A_PROJECT")


def derive_project_type(files):
    """Return the PROJECT_TYPE for an iterable of ``(file_name, file_type)``.

    Pipeline-artifact files (our own ``metadata.json`` / ``metadata_ddi.xml``)
    are ignored automatically by :func:`classification.file_types.file_role`.
    """
    has_qda = False
    has_primary = False
    has_other = False

    for file_name, file_type in files:
        role = file_role(file_name, file_type)
        if role == "QDA":
            has_qda = True
            break          # QDA wins immediately, no need to look further
        elif role == "PRIMARY":
            has_primary = True
        elif role == "OTHER":
            has_other = True

    if has_qda:
        return "QDA_PROJECT"
    if has_primary:
        return "QD_PROJECT"
    if has_other:
        return "OTHER_PROJECT"
    return "NOT_A_PROJECT"
