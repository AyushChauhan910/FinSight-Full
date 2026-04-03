import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders finsight header', () => {
  render(<App />);
  const heading = screen.getByText(/FINSIGHT/i);
  expect(heading).toBeInTheDocument();
});
