import React from 'react';
import Dashboard from '../../components/Dashboard/Dashboard';

const Landing: React.FC = () => {
  return (
    <div>
      <h1>Trace Backend API Tester</h1>
      <p>Test your backend endpoints directly from this interface.</p>
      <Dashboard />
    </div>
  );
};

export default Landing;