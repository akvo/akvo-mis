.. raw:: html

    <style>
      .bolditalic {font-style: italic; font-weight: 700;}
      .heading {font-size: 34px; font-weight: 700;}
    </style>

.. role:: heading

:heading:`Data Management`

.. role:: bolditalic


Registering Data
-----------------

1. From the Sidebar of the control center, click the :bolditalic:`Manage Data` menu to view and manage your registration data.

.. image:: ../assets/manage-data.png
   :alt: Manage Data
   :width: 100%

2. Select the questionnaire you want to register data for from the dropdown menu. Then click the :bolditalic:`Add New` button to create a new data entry. This will redirect you to the Webforms page, where you can fill in the data for the selected questionnaire. 

.. image:: ../assets/manage-data-add.png
   :alt: Add new Data
   :width: 100%

3. Fill all the mandatory fields in the Webforms page and click the :bolditalic:`Submit` button to save the data. 

.. image:: ../assets/manage-data-webforms.png
   :alt: Webforms page
   :width: 100%

4. After saving the data, you will be redirected to the Thanking page, where you have 2 options:

   - **Add New Submission**: Redirects you back to the Webforms page to register a new data entry for the same questionnaire.
   - **Finish and Go to Manage Data**: Conditional option that appears if the questionnaire is automatically approved. It redirects you to the Manage Data page, where you can view the registered data.
   - **Finish and Go to Batch**: Conditional option that appears if the questionnaire is a pending submission. It redirects you to the Batch page, where you can manage the batch submission.

.. image:: ../assets/manage-data-thanking-1.png
   :alt: Thanking Page 1
   :width: 100%

.. image:: ../assets/manage-data-thanking-2.png
   :alt: Thanking Page 2
   :width: 100%

5. In the Manage Data page, you can filter the data by questionnaire and administration.

.. image:: ../assets/manage-data-list.png
   :alt: Registered Data List
   :width: 100%

6. To view, edit or delete existing data, click on the row of the data you want to view. This will redirect you to the Monitoring page, where you can see the registered data along with the questionnaire details.

.. image:: ../assets/manage-data-view.png
   :alt: View Data
   :width: 100%


Editing Data
-------------

.. note::
   To edit data, you must have Super-admin privilege or have :ref:`form_access` - **Edit** permission.
   You can only edit data that has been registered in the system.

Make sure you already on the Monitoring page of the data you want to edit.

1. Click the data cell you want to edit. This will show the input field for the selected cell. Click the save button to append the changes. If there is a data that cannot be edited, then the input field will be disabled.

.. image:: ../assets/manage-data-edit-1.png
   :alt: Editing Data

2. If you have made changes to the data, you can click the **Reset** button to discard the changes.

.. image:: ../assets/manage-data-edit-2.png
   :alt: Resetting Data Changes
   :width: 100%

3. If all of the data is correct, you can click the **Save** button to save the changes.

.. image:: ../assets/manage-data-edit-3.png
   :alt: Saving Data Changes
   :width: 100%

Deleting data
--------------

.. note::
   Data deletion can only be performed by Super-admin privileges or by users with :ref:`form_access` - **Delete** permission.
   You can only delete data that has been registered in the system.

Make sure you already on the Monitoring page of the data you want to delete.

1. Click the :bolditalic:`Delete` button to delete the data. A confirmation dialog will appear asking you to confirm the deletion

.. image:: ../assets/manage-data-delete.png
   :alt: Deleting Data
   :width: 100%

2. Click the :bolditalic:`Delete` button on the confirmation dialog to delete the data. If you want to cancel the deletion, click the :bolditalic:`Cancel` button.

.. image:: ../assets/manage-data-delete-confirm.png
   :alt: Confirm Deletion
   :width: 100%


Monitoring Data
-----------------

Make sure you already on the Monitoring page of the data you want to monitor.

.. image:: ../assets/manage-data-monitoring.png
   :alt: Monitoring Data
   :width: 100%

Create a new data entry
=========================

1. Click the :bolditalic:`Update Data` button to create a new data entry. This will show a dropdown with the available monitoring questionnaires. Select the questionnaire you want to create a new data entry for.

.. image:: ../assets/manage-data-update.png
   :alt: Update Data
   :width: 100%

2. After selecting the questionnaire, you will be redirected to the Webforms page, where you can fill in the data for the selected questionnaire. Fill all the mandatory fields and click the :bolditalic:`Submit` button to save the data.

.. image:: ../assets/manage-monitoring-webforms.png
   :alt: Webforms page for Monitoring
   :width: 100%

3. After submitting the data, you will be redirected to the Monitoring page, where you can see the newly created data entry.    

.. image:: ../assets/manage-data-monitoring-new.png
   :alt: New Data Entry
   :width: 100%


Monitoring Overview
=========================

This page provides visual insights into the data collected through the selected Monitoring questionnaire.
The number, option and multiple option types of questions will be Y axis, while the X axis will be the date of the data collection. The chart will show the number of responses for each question type, allowing you to see trends and patterns in the data over time.


.. image:: ../assets/monitoring-overview.png
   :alt: Monitoring Data
   :width: 100%


Map View
-----------------

The Map View provides a visual representation of the data collected through the selected Monitoring questionnaire on a map. It allows you to see the geographical distribution of the data points, making it easier to identify patterns and trends in specific locations.

.. image:: ../assets/manage-data-map-view.png
   :alt: Map View
   :width: 100%

Number Types
====================

The Number Types section displays the different types of numerical responses collected in the selected Monitoring questionnaire. It provides insights into the variety of numerical data collected, helping you understand the distribution and trends in the data.

.. image:: ../assets/map-data-number-types.png
   :alt: Number Types
   :width: 100%


Option types
===============

The Option Types section displays the different types of options available in the selected Monitoring questionnaire. It provides insights into the variety of responses collected, helping you understand the diversity of data.

.. image:: ../assets/map-data-option-types.png
   :alt: Option Types
   :width: 100%


Multiple Option Types
=======================

The Multiple Option Types section displays the different types of multiple options available in the selected Monitoring questionnaire. It provides insights into the variety of multiple-choice responses collected, helping you understand the diversity of data.

.. image:: ../assets/map-data-multiple-option-types.png
   :alt: Multiple Option Types
   :width: 100%



Draft Submissions
------------------

Draft submissions are entries that have been started but not yet submitted. They allow users to save their progress and return later to complete the submission. This feature is particularly useful for Monitoring questionnaires that require detailed information or take time to complete, such as obtaining results from laboratory tests. Draft submissions are also synced with draft submissions from the Mobile application, enabling both channels to work seamlessly together.


.. image:: ../assets/manage-data-draft-submissions.png
   :alt: Draft Submissions
   :width: 100%

Create a new draft submission
===============================

1. Select the questionnaire you want to create a new draft submission for from the dropdown menu. Then Click the :bolditalic:`Add New` button to create a new draft submission. 

.. image:: ../assets/manage-draft-1.png
   :alt: Add New Draft Submission
   :width: 100%

2. After selecting the questionnaire, you will be redirected to the Webforms page, where you can fill in the data for the selected questionnaire. Fill any necessary fields and click the :bolditalic:`Save Draft` button to save the draft submission. There is no validation during draft submission, so you can save the draft without filling all the mandatory fields.

.. image:: ../assets/manage-draft-2.png
   :alt: Webforms page for Draft Submission
   :width: 100%

3. After saving the draft, you will be redirected to the Draft Submissions page, where you can see the newly created draft submission.

.. image:: ../assets/manage-draft-3.png
   :alt: New Draft Submission
   :width: 100%

Edit Draft Submission
==========================

Expand the toggle button next to the draft submission you want to edit. You will have two options:

1. Edit only: Continue editing the draft submission without validation.
2. Edit and Publish Draft: Continue editing the draft submission and validate it before publishing as a new data entry.

.. image:: ../assets/manage-draft-edit.png
   :alt: Edit Draft Submission
   :width: 100%

Delete Draft Submission
==========================

To delete a draft submission, expand the toggle button next to the draft submission you want to delete and click the :bolditalic:`Delete` button. A confirmation dialog will appear asking you to confirm the deletion.

.. image:: ../assets/manage-draft-delete.png
   :alt: Delete Draft Submission
   :width: 100%


Downloading data
-----------------

Select the questionnaire and use the :bolditalic:`Download Data` option to
export its submissions. You can choose to export all data or only the latest
(new or updated) data. The export is generated in the background; you collect
the finished file from the :doc:`Downloads page <download>`.

Dashboards and Reports
----------------------

Beyond the per-questionnaire :bolditalic:`Monitoring Overview` and
:bolditalic:`Map View` above, the platform provides aggregated
:bolditalic:`Dashboards` and generated :bolditalic:`Reports`, reached from the
dropdown in the top header (not the control-center sidebar):

- :bolditalic:`Dashboards` present charts and maps that summarise the collected
  data across administrative areas.
- :bolditalic:`Reports` let you choose a report template and generate a
  document (for example a ``.docx`` report) for a selected questionnaire and
  area. See the Outputs section for more on generated report documents.

.. note::
   Dashboards and report templates are configured per deployment, so the exact
   items available depend on your platform's configuration.
