# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Akvo MIS (Management Information System) is a Real Time Monitoring Information Systems platform with three main components:
- **Backend**: Django REST Framework API (Python 3.8.5)
- **Frontend**: React web application (Create React App)
- **Mobile App**: React Native mobile application (Expo)

## Architecture

### Multi-Tier Application Structure

The application is containerized using Docker Compose with the following services:
- `backend`: Django backend API server (port 8000)
- `worker`: Django-Q background worker for async tasks
- `frontend`: React development server (port 3000) / Nginx production server
- `db`: PostgreSQL 12 database (port 5432)
- `pgadmin`: Database administration UI (port 5050)

### Backend Architecture (Django)

Located in `./backend/`

#### API Structure
- Main API is versioned under `api/v1/`
- API modules organized by domain:
  - `v1_users/`: Authentication, user management, profiles
  - `v1_profile/`: Administration hierarchy, user roles, entity data
  - `v1_forms/`: Form definitions, questions, question groups
  - `v1_data/`: Form data submissions, answers, data approval
  - `v1_approval/`: Approval workflows and levels
  - `v1_jobs/`: Background job management
  - `v1_files/`: File uploads and downloads
  - `v1_mobile/`: Mobile app specific endpoints
  - `v1_visualization/`: Charts and maps data

#### Key Django Patterns
- **Custom Model Managers**: `SoftDeletes` and `Draft` mixins provide soft delete and draft functionality
  - Models using these have custom managers: `objects`, `objects_deleted`, `objects_draft`
  - Located in: `utils/soft_deletes_model.py`, `utils/draft_model.py`
- **Custom Permissions**: CASL-based permission system in `utils/custom_permissions.py`
- **Data Access Types**: Form data has approval workflows with different access levels (view, submit, approve)

#### Database
- PostgreSQL 12 with schema name `mis`
- DBML diagram auto-generated in `backend/db.dbml`
- Administration hierarchy supports multi-level geographic/organizational structure
- Form data supports parent-child relationships for complex forms

#### Utilities
Key utility modules in `backend/utils/`:
- `custom_generator.py`: Dynamic data generation
- `email_helper.py`: Email sending via Mailjet
- `export_form.py`: Form export functionality
- `report_generator.py`: Report generation with Excel/DOCX
- `storage.py`: Google Cloud Storage integration
- `upload_administration.py` / `upload_entities.py`: CSV data import

### Frontend Architecture (React)

Located in `./frontend/`

#### Key Technologies
- React 17 with React Router v6
- Ant Design v4 for UI components
- Pullstate for state management
- Akvo custom components: `akvo-react-form`, `akvo-charts`
- ECharts for data visualization
- Leaflet for maps
- CASL for permissions (`@casl/ability`, `@casl/react`)

#### Page Structure
Pages in `src/pages/`:
- `login/`: Authentication
- `home/`: Dashboard
- `control-center/`: Admin panel
- `forms/`: Form management
- `manage-data/`: Data entry and management
- `manage-draft/`: Draft submissions
- `approvals/`: Approval workflow
- `downloads/`: Data export
- `bi/`: Business intelligence/reporting
- `users/`, `master-data/`, etc.

#### Proxy Configuration
- Development uses `setupProxy.js` to proxy `/api/*` to backend:8000
- Production uses Nginx configuration in `frontend/nginx/conf.d/default.conf`

#### Frontend ESLint Rules
Config in `frontend/.eslintrc.json` — key rules to respect when writing JS/JSX in `frontend/src/`:
- **`"curly": "error"`**: every `if/else/for/while` body MUST use braces, even for single statements. `if (!x) return;` ❌ → `if (!x) { return; }` ✅
- **`"no-undefined": "warn"`**: do not reference the `undefined` identifier. Use bare `return;` instead of `return undefined;`. Do not use `void 0` or explicit `x === undefined` (use `typeof` or falsy checks)
- **`"prefer-arrow-callback": "error"`**: callbacks passed to functions must be arrow functions
- **`"prefer-const": "warn"`**: use `const` for variables that are not reassigned
- **`"no-console": "warn"`** with `allow: ["error", "info"]`: avoid `console.log`/`console.warn` in committed code
- **`eslint:recommended` + `plugin:react/recommended` + `plugin:prettier/recommended`**: all defaults apply — prettier formatting is enforced
- When an early-return inside a function that also returns a cleanup/value, either return a no-op of the same shape (e.g., `return () => {};` in `useEffect`) or restructure so the function only returns one kind of value. Do not disable lint rules with `// eslint-disable-next-line` — fix the code to satisfy the rule

Do not produce code that trips any of the above. Run `./dc.sh exec -T frontend npx eslint <path>` in the frontend container (NOT host) to verify.

#### Form System (akvo-react-form)

The frontend uses `akvo-react-form` (v2.7.0) - a custom Akvo library for building dynamic webforms.

**Repository**: https://github.com/akvo/akvo-react-form

**Key Features**:
- Dynamic form rendering from JSON definitions
- Multilingual support
- Complex conditional logic and dependencies
- Progress tracking
- Draft autosave functionality
- Initial value pre-population
- Field validation
- Repeatable question groups

**Supported Question Types**:
1. `input`: Text input fields
2. `number`: Numeric input with validation
3. `cascade`: Cascading dropdown selections
4. `text`: Multi-line text area
5. `date`: Date picker
6. `option`: Single-choice radio buttons
7. `multiple_option`: Multi-choice checkboxes
8. `tree`: Tree select for hierarchical data
9. `table`: Table input for structured data
10. `autofield`: Auto-populated computed fields
11. `photo`: Image upload
12. `entity`: Entity cascade (dropdown with API integration)
13. `attachment`: File attachment upload
14. `signature`: Digital signature capture
15. `geo`: Geolocation capture
16. `administration`: Administration hierarchy selector

**Basic Usage** (see `frontend/src/pages/forms/Forms.jsx`):
```javascript
import { Webform } from 'akvo-react-form';
import 'akvo-react-form/dist/index.css';

<Webform
  formRef={webformRef}
  forms={forms}                    // Form definition from backend API
  onFinish={submitFormData}        // Called on form submission
  onCompleteFailed={onFinishFailed}// Called on validation failure
  onChange={onChange}              // Called on field value changes
  submitButtonSetting={{ loading: submit }}
  languagesDropdownSetting={{ showLanguageDropdown: false }}
  initialValue={initialValue}      // Pre-populate form values
/>
```

**Form Definition Structure**:
Forms fetched from `/form/web/:formId` endpoint with structure:
- `question_group[]`: Array of question groups
  - `name`: Group name
  - `description`: Optional description
  - `repeatable`: Boolean for repeatable groups
  - `repeat_text`: Text for repeat button
  - `question[]`: Array of questions
    - `id`: Question ID
    - `name`: Question identifier
    - `label`: Display label
    - `type`: Question type (see types above)
    - `required`: Boolean
    - `meta`: Boolean (used for datapoint naming)
    - `tooltip`: Optional help text
    - `extra`: Additional configuration (API endpoints, options, etc.)
    - `dependency[]`: Conditional display rules
    - `rule`: Validation rules

**Key Patterns**:
- **Entity Cascade**: Questions with `extra.type === 'entity'` are transformed to cascade type with API integration for dynamic options
- **Repeatable Groups**: Question groups with `repeatable: true` allow users to add multiple instances
- **Monitoring Forms**: Forms with parent relationships pre-fill data from parent submissions
- **Hidden Questions**: Questions with `hidden: true` are filtered out during rendering
- **File Uploads**: Photo and attachment questions upload files to backend before form submission
- **Datapoint Naming**: Questions with `meta: true` contribute to the datapoint name generation

**Form Submission Flow**:
1. User fills out form with validations
2. On submit, required fields validated
3. File uploads processed (photos, attachments, signatures)
4. Entity cascade values transformed
5. Repeatable question answers collected with index
6. Answers grouped and sent to `POST /form-pending-data/:formId`
7. Draft cleared from localStorage
8. Success message displayed

**Draft Management**:
- akvo-react-form includes built-in autosave to localStorage
- Drafts filtered per form using `formId` parameter
- Cleared on successful submission or manual reset

### Mobile App Architecture (React Native + Expo)

Located in `./app/`

#### Key Technologies
- React Native 0.79.2 with React 19
- Expo SDK 53
- React Navigation for routing
- React Native Elements (RNEUI) for UI
- SQLite for local data storage (`expo-sqlite`)
- Formik + Yup for form validation
- Pullstate for state management
- Sentry for error tracking

#### Structure
- `src/pages/`: Main screens (Home, FormPage, Submission, Settings, etc.)
- `src/database/`: SQLite database management
- `src/form/`: Form rendering and management
- `src/components/`: Reusable UI components
- `src/lib/`: Utilities and helpers
- `src/store/`: Pullstate stores
- `src/navigation/`: Navigation configuration

#### Offline-First Design
- Uses SQLite for local storage of forms and submissions
- Background sync with backend via `expo-background-fetch` and `expo-task-manager`
- Network state monitoring with `@react-native-community/netinfo`

#### ESLint Rules (Airbnb config)
The mobile app extends `airbnb` ESLint. Key rules to follow when writing JS in `app/`:
- **No `for...of` loops** (`no-restricted-syntax`): Use `.reduce()`, `.map()`, `.forEach()`, or `.filter()` instead
- **No `await` in loops** (`no-await-in-loop`): For sequential async processing, use the reduce pattern:
  ```javascript
  // CORRECT: sequential async with reduce
  await items.reduce(async (prev, item) => {
    await prev;
    await doSomething(item);
  }, Promise.resolve());

  // WRONG: for...of with await
  for (const item of items) { await doSomething(item); }

  // WRONG: forEach with async (fire-and-forget, doesn't await)
  items.forEach(async (item) => { await doSomething(item); });
  ```
- **Arrow functions for components** (`react/function-component-definition`): Named and unnamed components must use arrow functions or function expressions
- **No param reassign** except props (`no-param-reassign`): Pullstate `.update((s) => { s.field = value })` is allowed

## Development Commands

### Initial Setup

1. Copy `.env` file:
```bash
cp env.example .env
# Edit .env with required configuration
```

2. Create Docker volume:
```bash
docker volume create akvo-mis-docker-sync
```

3. Start services:
```bash
./dc.sh up -d
```

4. Seed initial data:
```bash
./dc.sh exec backend ./seeder.sh
```

The seeder script prompts for:
- Seed administrative data (geographic/organizational hierarchy)
- Add super admin user
- Seed forms
- Seed organization data
- Seed administration attributes
- Generate fake data for testing

Default fake user password: `Test#123`

### Backend Development

#### Running the Backend
```bash
./dc.sh up -d backend
./dc.sh logs --follow backend
```

#### Django Management Commands
```bash
./dc.sh exec backend python manage.py <command>
```

Common commands:
- `makemigrations`: Create new migrations
- `migrate`: Apply migrations
- `createsuperuser --email <email>`: Create admin user
- `form_seeder`: Seed form definitions
- `administration_seeder`: Seed administration hierarchy
- `generate_config`: Generate mobile app config
- `generate_sqlite`: Generate SQLite databases for mobile app
- `clear_cache`: Clear Django cache

#### Testing Backend
```bash
# Run all tests with coverage
./dc.sh exec backend python manage.py test

# Run specific test module
./dc.sh exec backend python manage.py test api.v1.v1_profile.tests.test_administration_attributes

# Run tests with coverage (like CI)
./dc.sh exec backend coverage run --rcfile=./.coveragerc manage.py test --shuffle --parallel 4
./dc.sh exec backend coverage report -m
```

#### Linting Backend
```bash
./dc.sh exec backend flake8
```

Configuration in `backend/setup.cfg` and `backend/pylsp.toml`

### Frontend Development

#### Running the Frontend
```bash
./dc.sh up -d frontend
./dc.sh logs --follow frontend
```

Frontend runs at http://localhost:3000

#### Testing Frontend
```bash
cd frontend

# Run tests in watch mode
npm test

# Run tests with coverage (CI mode)
npm run test:ci
```

#### Linting Frontend
```bash
cd frontend
npm run lint
npm run prettier
```

Configuration in `frontend/.eslintrc.json`

### Mobile App Development

#### Setup
```bash
# Create mobile volume
docker volume create akvo-mis-mobile-docker-sync

# Start mobile dev server
./dc-mobile.sh up -d
```

#### Testing on Device
1. Install Expo Go app on Android device
2. Connect device to same WiFi network
3. Open Expo Go and enter URL: `<Your_IP_Address>:19000`

#### Mobile App Commands
```bash
cd app

# Start development server
npm start

# Run on Android emulator
npm run android

# Run tests
npm test
npm run test:watch

# Linting
npm run lint
npm run prettier-check
npm run prettier-write

# EAS Build (Production)
npm run eas-cli:develop    # Development build
npm run eas-cli:release    # Production build
```

#### Updating Mobile Version
```bash
./update-mobile-version.sh
```

## Production Build

### Local Production Build
```bash
export CI_COMMIT='local'
./ci/build.sh
```

This generates Docker images:
- `eu.gcr.io/akvo-lumen/akvo-mis/backend:latest`
- `eu.gcr.io/akvo-lumen/akvo-mis/frontend:latest`
- `eu.gcr.io/akvo-lumen/akvo-mis/worker:latest`

### Running Production Build
```bash
docker-compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

## Testing

### Backend Tests
- Tests located in `backend/api/v1/*/tests/`
- Uses Django's test framework with parallel execution
- Run with: `python manage.py test --shuffle --parallel 4`
- Coverage configured in `backend/.coveragerc`

### Frontend Tests
- Tests in `frontend/src/**/__test__/` and `*.test.js` files
- Uses React Testing Library + Jest
- Mock setup in `frontend/src/setupTests.js`

### Mobile Tests
- Tests in `app/src/pages/__tests__/`
- Uses React Native Testing Library + Jest
- Configuration in `app/jest.config.js`

## Key Workflows

### Form Data Submission Flow
1. Forms defined in `v1_forms` with questions organized in question groups
2. Mobile/web submits data to `v1_data` endpoints
3. Data stored in `FormData` model with related `Answers`
4. Approval workflow triggered if form has approvers (checked via `has_approval` property)
5. Data synced to cloud storage and SQLite for mobile apps

### Administration Hierarchy
- Multi-level geographic/organizational structure
- Used for user access control and data filtering
- Supports path-based queries for ancestor/descendant relationships

### Background Jobs
- Django-Q used for async tasks
- Worker service runs `./run_worker.sh`
- Jobs managed through `v1_jobs` API

## Environment Variables

Key variables in `.env`:
- `DB_*`: Database connection settings
- `DJANGO_SECRET`: Django secret key
- `DEBUG`: Enable debug mode
- `GOOGLE_APPLICATION_CREDENTIALS`: GCS credentials path
- `MAILJET_*`: Email service credentials
- `SENTRY_*`: Error tracking configuration
- `EXPO_TOKEN`: Expo build token
- `IP_ADDRESS`: Mobile device endpoint URL
- `STORAGE_PATH`: Local storage path

## Documentation

- API documentation auto-generated with drf-spectacular
- Database schema documentation at dbdocs.io (auto-updated on main/develop)
- ReadTheDocs: https://akvo-mis.readthedocs.io/

## Helper Scripts

- `./dc.sh`: Docker Compose wrapper for main app
- `./dc-mobile.sh`: Docker Compose wrapper for mobile dev
- `./seeder.sh`: Data seeding script
- `./release.sh`: Release preparation script
- `./update-mobile-version.sh`: Mobile version management
- `./generate_config.sh`: Generate config files

## Git Workflow

### Branch Naming Convention

Feature branches follow the pattern: `feature/<issue-number>-<description>`

Example: `feature/136-allow-moving-between-question-groups`

**Important**: The issue number after the slash should be used in commit messages when closing issues.

### Commit Message Format

Commit messages follow this format:

```bash
git commit -m "[#<issue-number>] <Subject line>

<body with bullet points describing changes>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Example**:
```bash
git commit -m "[#136] Allow free navigation between form groups with visual indicators

- Remove navigation blocking when required fields are unanswered
- Allow users to freely move between question groups using Next/Back buttons
- Add validation for all groups before final submission
- Implement color-coded visual indicators in question group list

This improves UX by giving users flexibility to complete forms in any order
while maintaining data integrity through comprehensive validation on submit.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Design Documents

Before implementing new features, check for existing design documents:

### Location
- **Design docs**: `doc/design/` - Approved feature designs
- **Templates**: `doc/templates/` - Templates for new features
- **Feature specs**: `doc/akvo-mis-initiative/` - Feature task breakdowns

### Key Design Documents
- `doc/design/FB-001-form-builder-data-architecture.md` - Form builder data model, versioning, and API design
- `doc/templates/FEATURE_DESIGN_TEMPLATE.md` - Template for new feature designs

### When to Create Design Documents
Create a design document (using the template) BEFORE implementation when:
- Adding new database models or fields
- Designing new API endpoints
- Making architectural decisions
- Changes affect mobile sync or backward compatibility

### Reading Design Documents
When implementing a feature, always check if a design document exists:
```bash
ls doc/design/
cat doc/design/<feature-name>.md
```
