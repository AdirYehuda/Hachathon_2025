import React, { useState } from 'react';
import {
  Box,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Chip,
  OutlinedInput,
  FormHelperText,
  Alert
} from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';

const RESOURCE_TYPES = [
  'EC2', 'RDS', 'S3', 'EBS', 'Lambda', 'ELB', 'CloudFront', 'ElastiCache'
];

const TIME_RANGES = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
  { value: '6m', label: '6 months' },
  { value: '1y', label: '1 year' }
];

const QueryForm = ({ onAddQuery, disabled }) => {
  const [query, setQuery] = useState('');
  const [timeRange, setTimeRange] = useState('30d');
  const [resourceTypes, setResourceTypes] = useState([]);
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!query.trim()) {
      setError('Please enter a query');
      return;
    }

    if (query.trim().length < 10) {
      setError('Query must be at least 10 characters long');
      return;
    }

    // Sanitize query - remove HTML-like tags and invalid characters
    const sanitizedQuery = query
      .replace(/<[^>]*>/g, '') // Remove HTML tags
      .replace(/[<>"']/g, '') // Remove remaining invalid characters
      .replace(/\s+/g, ' ') // Normalize whitespace
      .trim();

    if (!sanitizedQuery || sanitizedQuery.length < 10) {
      setError('Query must be at least 10 characters long after sanitization');
      return;
    }

    if (sanitizedQuery.length > 1000) {
      setError('Query must be less than 1000 characters');
      return;
    }

    // Add query
    onAddQuery({
      query: sanitizedQuery,
      timeRange,
      resourceTypes
    });

    // Reset form
    setQuery('');
    setTimeRange('30d');
    setResourceTypes([]);
  };

  const handleResourceTypesChange = (event) => {
    const value = event.target.value;
    setResourceTypes(typeof value === 'string' ? value.split(',') : value);
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Query Input */}
      <TextField
        fullWidth
        label="Cost Optimization Query"
        multiline
        rows={3}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={disabled}
        placeholder="e.g., Analyze EC2 instances for cost optimization opportunities in production environment"
        helperText="Describe what you want to analyze for cost optimization"
        sx={{ mb: 2 }}
      />

      {/* Time Range */}
      <FormControl fullWidth sx={{ mb: 2 }}>
        <InputLabel>Time Range</InputLabel>
        <Select
          value={timeRange}
          label="Time Range"
          onChange={(e) => setTimeRange(e.target.value)}
          disabled={disabled}
        >
          {TIME_RANGES.map((range) => (
            <MenuItem key={range.value} value={range.value}>
              {range.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Resource Types */}
      <FormControl fullWidth sx={{ mb: 2 }}>
        <InputLabel>Resource Types (Optional)</InputLabel>
        <Select
          multiple
          value={resourceTypes}
          onChange={handleResourceTypesChange}
          input={<OutlinedInput label="Resource Types (Optional)" />}
          disabled={disabled}
          renderValue={(selected) => (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {selected.map((value) => (
                <Chip key={value} label={value} size="small" />
              ))}
            </Box>
          )}
        >
          {RESOURCE_TYPES.map((type) => (
            <MenuItem key={type} value={type}>
              {type}
            </MenuItem>
          ))}
        </Select>
        <FormHelperText>
          Leave empty to analyze all resource types
        </FormHelperText>
      </FormControl>

      {/* Submit Button */}
      <Button
        type="submit"
        variant="contained"
        startIcon={<AddIcon />}
        disabled={disabled || !query.trim()}
        fullWidth
      >
        Add Query
      </Button>
    </Box>
  );
};

export default QueryForm; 