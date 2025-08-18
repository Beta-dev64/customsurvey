# Dangote Cement Execution Tracker

A web application prototype for tracking outlet execution activities for Dangote Cement in Nigeria.

## Features

1. **Pre-populated Outlet Database** - The system comes with an existing database of Dangote Cement outlets across Nigeria.

2. **Execution Capture** - Field agents can:
   - Login to the system
   - Select outlets to perform executions
   - Capture before and after images
   - Automatically record geolocation data
   - Document product availability
   - Add notes and observations

3. **Dashboard** - Interactive dashboard with:
   - Key metrics and statistics
   - Execution over time visualization
   - Regional breakdown of outlets
   - Outlet type distribution
   - Agent performance metrics

4. **Reporting** - Generate detailed reports:
   - Product availability analysis
   - Execution coverage statistics
   - Before and after image comparison
   - Regional performance analysis

5. **Responsive Design** - Works on both desktop and mobile devices for field agents

## Technical Details

### Technologies Used

- **Backend**: Flask (Python)
- **Database**: SQLite (for prototype; would be migrated to a more robust solution for production)
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Visualization**: Chart.js
- **Geolocation**: HTML5 Geolocation API
- **Camera Access**: MediaDevices API

### Database Schema

1. **Outlets Table**
   - Contains outlet information (URN, name, address, type, location, etc.)
   - Pre-populated with sample data

2. **Users Table**
   - Stores user credentials and roles
   - Supports different user types (admin, field agent)

3. **Executions Table**
   - Records execution details
   - Links to before/after images
   - Stores geolocation data
   - Contains product availability information

## Getting Started

### Demo Credentials

- **Admin**: 
  - Username: admin
  - Password: admin123

- **Field Agent**: 
  - Username: agent1
  - Password: agent123

### Running the Application

1. Install dependencies:
   ```
   pip install flask pandas
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Access the application at `http://localhost:5000`

## Future Enhancements

1. **AI Image Analysis** - Implement AI/ML to automatically compare before/after images for compliance

2. **Advanced Analytics** - More sophisticated reporting and predictive analytics

3. **Offline Mode** - Allow field agents to capture executions offline and sync when connectivity is available

4. **Mobile App** - Native mobile applications for Android and iOS

5. **Integration** - Connect with other Dangote systems for seamless data flow

## Screenshots

(Screenshots would be added here in a real README)

## License

This is a prototype application. All rights reserved.

## Contact

For more information, please contact the development team.