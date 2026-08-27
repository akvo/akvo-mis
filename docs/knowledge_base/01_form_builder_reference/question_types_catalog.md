# Question Types & Schema Attribute Catalog

This document is the definitive reference for all question types and their configuration attributes in the Akvo MIS Form Builder and `akvo-react-form` runtime.

## Complete Question Types Catalog

### 1. Text / Input (`input`)
- **Description**: Single-line text field for short text responses.
- **Common Use Cases**: First/Last Name, National ID, Phone Number, Serial Number, Short Code.
- **Supported Settings & Attributes**:
  - `label` (string, required): The question text displayed to the respondent.
  - `name` / `variable_name` (string, required): Unique internal identifier for data storage and exports.
  - `tooltip` (string, optional): Helper text or instructions shown below the question.
  - `required` (boolean): Whether answering is mandatory before form submission.
  - `double_entry` (boolean): When enabled, prompts the respondent to type the answer twice to prevent typos.
  - `mask` / `password` (boolean): Masks entered characters with dots and provides a show/hide eye toggle.
  - `addonBefore` (string): Text or symbol prefix placed immediately before the input box (e.g. `+62`, `$`, `ID:`). Text only, no images/icons.
  - `addonAfter` (string): Text or symbol suffix placed immediately after the input box (e.g. `cm`, `kg`, `%`).
  - `max_length` (number): Maximum allowable character count.
  - `pre` (string/object): JSON schema setting for copying answer from an earlier question in the same session.

### 2. Multi-line Text / Memo (`text`)
- **Description**: Multi-line expandable text area for longer descriptive responses.
- **Common Use Cases**: General observations, meeting notes, incident descriptions, feedback, addresses.
- **Supported Settings**:
  - `label`, `name`, `tooltip`, `required`, `max_length`, `extra`.

### 3. Number (`number`)
- **Description**: Numeric input supporting integers or decimal values.
- **Common Use Cases**: Age, household member count, price, area, crop yield, water flow rate, temperature.
- **Supported Settings & Attributes**:
  - `min` (number): Minimum allowable numerical value. Values below this trigger validation errors.
  - `max` (number): Maximum allowable numerical value. Values above this trigger validation errors.
  - `decimal` / `allow_decimal` (boolean): Allows decimal point entry (e.g. 3.14).
  - `addonBefore` (string): Currency symbol or prefix (e.g. `$`, `€`, `Rp`). Plain text only.
  - `addonAfter` (string): Unit of measurement (e.g. `hectares`, `litres/min`, `°C`, `kg`).
  - `double_entry` (boolean): Re-prompts the respondent to verify critical numeric figures.

### 4. Single Choice / Radio (`option`)
- **Description**: Displays a list of mutually exclusive choices where the respondent selects exactly one.
- **Common Use Cases**: Gender, Yes/No questions, Status ratings, Facility condition, Water source type.
- **Options Structure**:
  - Each choice contains `value` (internal code), `label` (display text), and optional `color` (hex code).
- **Color Tagging**:
  - `color` (hex string, e.g. `#28A745`, `#DC3545`): Renders a colored pill/tag next to the option choice in web forms. Purely a visual aid.
- **Other Choice Option**: Can include an open-ended "Other (please specify)" text entry when selected.

### 5. Multiple Choice / Checkbox (`multiple_option`)
- **Description**: Allows the respondent to select one or multiple choices from a predefined list.
- **Common Use Cases**: Crops grown, symptoms observed, sanitation facilities available, languages spoken.
- **Supported Settings**:
  - `options` array (with `label`, `value`, `color`), `min_selected`, `max_selected`.

### 6. Cascade Dropdown (`cascade`)
- **Description**: Hierarchical cascading dropdowns where selecting a parent narrows down choices in child levels.
- **Common Use Cases**: Administrative hierarchy (Country > Province > District > Village), Health hierarchy (Region > Facility Type > Health Center).
- **Data Source**: Configured via a master cascade list or CSV data source in Akvo MIS Control Center.

### 7. Geopoint / Location (`geo`)
- **Description**: Captures geographic coordinates (Latitude, Longitude, and optional Altitude/Accuracy).
- **Web vs Mobile Behavior**:
  - **Mobile App**: Uses device hardware GPS chip to lock high-precision coordinates with accuracy thresholds.
  - **Web Form**: Uses browser HTML5 Geolocation API or interactive map pin dropper.

### 8. Photo / Image (`photo`)
- **Description**: Image capture or file upload.
- **Web vs Mobile Behavior**:
  - **Mobile App**: Launches the camera to capture a new photo in the field, timestamped with metadata.
  - **Web Form**: Allows image file selection (JPEG, PNG).

### 9. Digital Signature (`signature`)
- **Description**: Interactive hand-drawn touch/mouse signature pad.
- **Common Use Cases**: Enumerator verification, respondent consent confirmation, supervisor sign-off.

### 10. File Attachment (`attachment`)
- **Description**: Upload non-image files such as PDF documents, spreadsheets, or scanned certificates.

### 11. Autofield / Computed (`autofield`)
- **Description**: Read-only field calculated automatically from other question values using a mathematical formula.
- **Common Use Cases**: Total cost (`[q_qty] * [q_price]`), BMI score (`[weight] / ([height] * [height])`), Age in years.

### 12. Date & Time (`date`)
- **Description**: Calendar date and time picker. Supports date format customization and Min/Max date constraints (e.g. cannot select future dates for birth date).

### 13. Administration (`admin`) & Tree Hierarchy (`tree`)
- **Description**: Selectors linked to tenant administration levels and nested taxonomies configured in Akvo MIS.
