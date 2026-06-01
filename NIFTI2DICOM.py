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
    print(f"NIfTI intensity range after normalization: min={nifti_data.min()}, max={nifti_data.max()}")

    os.makedirs(output_dicom_dir, exist_ok=True)

    # Accept DICOM files regardless of extension
    all_files = [os.path.join(dicom_template_dir, f)
                 for f in os.listdir(dicom_template_dir)
                 if os.path.isfile(os.path.join(dicom_template_dir, f))]
    dicom_files = [f for f in all_files if pydicom.misc.is_dicom(f)]

    if not dicom_files:
        raise ValueError(f"No DICOM files found in {dicom_template_dir}")

    # Sort by InstanceNumber to guarantee correct anatomical slice ordering
    dicom_files.sort(key=lambda f: int(pydicom.dcmread(f, stop_before_pixels=True).InstanceNumber))

    new_series_instance_uid = generate_uid()

    if orientation == 'axial' and len(dicom_files) != nifti_data.shape[2]:
        raise ValueError(f"Slice count mismatch (axial): {len(dicom_files)} DICOM vs {nifti_data.shape[2]} NIfTI")
    elif orientation == 'sagittal' and len(dicom_files) != nifti_data.shape[0]:
        raise ValueError(f"Slice count mismatch (sagittal): {len(dicom_files)} DICOM vs {nifti_data.shape[0]} NIfTI")
    elif orientation == 'coronal' and len(dicom_files) != nifti_data.shape[1]:
        raise ValueError(f"Slice count mismatch (coronal): {len(dicom_files)} DICOM vs {nifti_data.shape[1]} NIfTI")

    for i, dicom_file in enumerate(dicom_files):
        dicom_template = pydicom.dcmread(dicom_file)

        if orientation == 'axial':
            nifti_slice = nifti_data[:, :, i]
        elif orientation == 'sagittal':
            nifti_slice = nifti_data[i, :, :]
        elif orientation == 'coronal':
            nifti_slice = nifti_data[:, i, :]
        else:
            raise ValueError(f"Invalid orientation '{orientation}': must be axial, sagittal, or coronal")

        # NOTE: This transform is validated for axial orientation.
        # Verify visually if using sagittal or coronal — the correct rotation
        # depends on the scanner convention and NIfTI affine for those planes.
        nifti_slice = np.rot90(nifti_slice, k=1)
        nifti_slice = nifti_slice[:, ::-1]

        if nifti_slice.shape != dicom_template.pixel_array.shape:
            raise ValueError(f"Shape mismatch at slice {i}: NIfTI {nifti_slice.shape} vs DICOM {dicom_template.pixel_array.shape}")

        dicom_template.PixelData = nifti_slice.astype(np.uint16).tobytes()

        dicom_template.SeriesNumber = sequence_number
        dicom_template.SeriesDescription = sequence_description
        dicom_template.ProtocolName = sequence_description
        dicom_template.SeriesInstanceUID = new_series_instance_uid
        dicom_template.SOPInstanceUID = generate_uid()

        # 12-bit data stored in 16-bit container
        dicom_template.BitsAllocated = 16
        dicom_template.BitsStored = 12
        dicom_template.HighBit = 11
        dicom_template.PixelRepresentation = 0

        base_name = os.path.basename(dicom_file)
        name_parts = base_name.split('-')
        if len(name_parts) > 3:
            new_name = f"{name_parts[0]}-{sequence_number}-{name_parts[2]}"
        else:
            new_name = f"IM-{sequence_number}-{base_name[-9:]}"

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
        print("Usage: python Nifti_To_DICOM.py <nifti> <dicom_dir> <out_dir> <orientation> <seq_num> <seq_desc>")
        sys.exit(1)

    nifti_file = sys.argv[1]
    dicom_template_dir = sys.argv[2]
    output_dicom_dir = sys.argv[3]
    orientation = sys.argv[4]
    sequence_number = int(sys.argv[5])
    sequence_description = sys.argv[6]

    nifti_to_dicom(nifti_file, dicom_template_dir, output_dicom_dir, sequence_number, sequence_description, orientation)
