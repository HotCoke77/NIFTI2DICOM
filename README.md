# NIFTI2DICOM

A Python script that replaces pixel data in DICOM files with intensities from a processed NIfTI image, while preserving all original DICOM metadata (patient info, series geometry, scanner parameters, etc.).

## Use case

Typical workflow in medical imaging research:

1. Export original MRI series as DICOM
2. Process the volume in NIfTI format (e.g., segmentation, registration, post-processing)
3. Use this script to embed the processed NIfTI intensities back into the original DICOM shells, producing a DICOM series that can be loaded into a PACS or viewer alongside the original data

## Requirements

- Python 3.7+
- See [requirements.txt](requirements.txt)

```bash
pip install -r requirements.txt
```

## Usage

```bash
python NIFTI2DICOM.py <input_nifti> <dicom_template_dir> <output_dicom_dir> <orientation> <seq_number> <seq_description>
```

| Argument | Description |
|---|---|
| `input_nifti` | Path to the processed NIfTI file (`.nii` or `.nii.gz`) |
| `dicom_template_dir` | Directory containing the original DICOM series (used as metadata template) |
| `output_dicom_dir` | Directory where output DICOM files will be written (created if absent) |
| `orientation` | Acquisition plane: `axial`, `sagittal`, or `coronal` |
| `seq_number` | Series number assigned to the output series (integer) |
| `seq_description` | Series description / protocol name for the output series |

### Example

```bash
python NIFTI2DICOM.py \
    input.nii.gz \
    /path/to/dicom_template/ \
    /path/to/output/ \
    axial \
    100 \
    MySeriesDescription
```

```bash
python NIFTI2DICOM.py \
    Target.nii.gz \
    ../DICOM/40_t1_mprage_tra_post/ \
    ../DICOM/Output \
    axial \
    1000 \
    BiopsyTarget
```

## Notes

- **Intensity normalization**: NIfTI intensities are linearly normalized to 0–1000 by default (configurable via `max_value` in `normalize_to_max`). This is appropriate for derived/processed images. For quantitative MRI (T1/T2 maps, ADC, etc.), consider preserving the original intensity scale.
- **Slice ordering**: DICOM files are sorted by `InstanceNumber` tag to ensure correct anatomical slice ordering.
- **Orientation transform**: The rot90 + left-right flip transform has been validated for axial orientation. Verify output visually if using sagittal or coronal data, as the correct transform depends on the scanner convention and NIfTI affine.
- **DICOM compatibility**: The script sets `BitsAllocated=16`, `BitsStored=12`, `HighBit=11` (12-bit data in a 16-bit container), which is a common convention for MRI.
- **Input matching**: The NIfTI file must be derived from the same MPR/orientation as the reference DICOM series, otherwise slice geometry will be misregistered.
