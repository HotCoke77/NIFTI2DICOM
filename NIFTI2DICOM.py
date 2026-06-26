#! /usr/bin/env python
import os
import pydicom
import nibabel as nib
import numpy as np
import sys
from pydicom.uid import generate_uid


def normalize_to_max(image, max_value=1000):
    img_min = np.min(image)
    img_max = np.max(image)
    if img_max == img_min:
        return np.zeros_like(image, dtype=np.uint16)
    norm_img = (image - img_min) / (img_max - img_min)
    norm_img = (norm_img * max_value).astype(np.uint16)
    return norm_img


def nifti_to_dicom(nifti_file, dicom_template_dir, output_dicom_dir, sequence_number, sequence_description, orientation='axial'):
    nifti_img = nib.load(nifti_file)
    nifti_data = nifti_img.get_fdata()
    nifti_data = normalize_to_max(nifti_data)
    affine = nifti_img.affine
    print(f"NIfTI intensity range after normalization: min={nifti_data.min()}, max={nifti_data.max()}")

    os.makedirs(output_dicom_dir, exist_ok=True)

    all_files = [os.path.join(dicom_template_dir, f)
                 for f in os.listdir(dicom_template_dir)
                 if os.path.isfile(os.path.join(dicom_template_dir, f))]
    dicom_files = [f for f in all_files if pydicom.misc.is_dicom(f)]

    if not dicom_files:
        raise ValueError(f"No DICOM files found in {dicom_template_dir}")

    # Map orientation to the relevant ImagePositionPatient axis and NIfTI voxel dimension.
    # DICOM uses LPS coordinates; NIfTI uses RAS.
    # z (superior) has the same sign in both; x and y are negated between the two conventions.
    if orientation == 'axial':
        dicom_axis = 2       # LPS z = RAS z (same sign)
        nifti_dim  = 2
        nifti_sign = float(affine[2, 2])
    elif orientation == 'sagittal':
        dicom_axis = 0       # LPS x = left; RAS x = right (opposite sign)
        nifti_dim  = 0
        nifti_sign = -float(affine[0, 0])
    elif orientation == 'coronal':
        dicom_axis = 1       # LPS y = posterior; RAS y = anterior (opposite sign)
        nifti_dim  = 1
        nifti_sign = -float(affine[1, 1])
    else:
        raise ValueError(f"Invalid orientation '{orientation}': must be axial, sagittal, or coronal")

    # Sort DICOM by ascending patient position along the slice axis
    dicom_files.sort(key=lambda f: float(pydicom.dcmread(f, stop_before_pixels=True).ImagePositionPatient[dicom_axis]))

    n_slices = nifti_data.shape[nifti_dim]
    if len(dicom_files) != n_slices:
        raise ValueError(f"Slice count mismatch ({orientation}): {len(dicom_files)} DICOM vs {n_slices} NIfTI")

    # If the NIfTI slice direction opposes the ascending DICOM position order, reverse the index
    nifti_reversed = nifti_sign < 0
    print(f"NIfTI slice order: {'reversed' if nifti_reversed else 'matched'} relative to DICOM position order")

    new_series_instance_uid = generate_uid()

    for i, dicom_file in enumerate(dicom_files):
        dicom_template = pydicom.dcmread(dicom_file)

        nifti_idx = (n_slices - 1 - i) if nifti_reversed else i

        if orientation == 'axial':
            nifti_slice = nifti_data[:, :, nifti_idx]
        elif orientation == 'sagittal':
            nifti_slice = nifti_data[nifti_idx, :, :]
        else:  # coronal
            nifti_slice = nifti_data[:, nifti_idx, :]

        # NOTE: This transform is validated for axial orientation.
        # Verify visually if using sagittal or coronal — the correct rotation
        # depends on the scanner convention and NIfTI affine for those planes.
        nifti_slice = np.rot90(nifti_slice, k=1)
        nifti_slice = nifti_slice[:, ::-1]

        if nifti_slice.shape != dicom_template.pixel_array.shape:
            raise ValueError(f"Shape mismatch at slice {i}: NIfTI {nifti_slice.shape} vs DICOM {dicom_template.pixel_array.shape}")

        dicom_template.PixelData = nifti_slice.astype(np.uint16).tobytes()

        dicom_template.SeriesNumber = sequence_number
        dicom_template.InstanceNumber = i + 1      # reassign sequentially in z-sort order
        dicom_template.SeriesDescription = sequence_description
        dicom_template.ProtocolName = sequence_description
        dicom_template.SeriesInstanceUID = new_series_instance_uid
        dicom_template.SOPInstanceUID = generate_uid()

        # 12-bit data stored in 16-bit container
        dicom_template.BitsAllocated = 16
        dicom_template.BitsStored = 12
        dicom_template.HighBit = 11
        dicom_template.PixelRepresentation = 0

        new_name = f"IM-{sequence_number}-{str(i + 1).zfill(4)}.dcm"

        output_file = os.path.join(output_dicom_dir, new_name)
        dicom_template.save_as(output_file)
        print(f"Saved: {output_file}")


if __name__ == "__main__":
    print()
    print("This script converts NIfTI intensities into original DICOM files, preserving all DICOM metadata.")
    print()
    print("!!! DICOM conversion rounds floats to integers — ensure intensity values are not decimals only")
    print("!!! Script will fail if the NIfTI was generated from a different MPR than the reference DICOM")
    print()
    print("Required packages: pydicom, nibabel, numpy")
    print()
    print("Usage:")
    print("  python <script_path> <input_nifti> <dicom_template_dir> <output_dicom_dir> <orientation> <seq_number> <seq_description>")
    print()
    print("Example:")
    print("  python NIFTI2DICOM.py input.nii.gz /path/to/dicom_template/ /path/to/output/ axial 100 MySeriesDescription")
    print("  python NIFTI2DICOM.py Target.nii.gz ../DICOM/40_t1_mprage_tra_post/ ../DICOM/Output axial 8888 BiopsyTarget")
    print()

    if len(sys.argv) < 7:
        print("Error: 6 arguments required.")
        print("Usage: python NIFTI2DICOM.py <nifti> <dicom_dir> <out_dir> <orientation> <seq_num> <seq_desc>")
        sys.exit(1)

    nifti_file = sys.argv[1]
    dicom_template_dir = sys.argv[2]
    output_dicom_dir = sys.argv[3]
    orientation = sys.argv[4]
    sequence_number = int(sys.argv[5])
    sequence_description = sys.argv[6]

    nifti_to_dicom(nifti_file, dicom_template_dir, output_dicom_dir, sequence_number, sequence_description, orientation)
