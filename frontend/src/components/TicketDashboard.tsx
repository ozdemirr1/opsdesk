import { useState } from 'react';
import type { TicketStatus, TicketSummary } from '../types/ticket';
import TicketDetail from './TicketDetail';
import TicketTable from './TicketTable';

type TicketDashboardProps = {
  tickets: TicketSummary[];
};

type FilterStatus = TicketStatus | 'all';

type StatusOption = {
  value: FilterStatus;
  label: string;
};

const STATUS_OPTIONS: readonly StatusOption[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
];

function isFilterStatus(value: string): value is FilterStatus {
  return STATUS_OPTIONS.some((option) => option.value === value);
}

export default function TicketDashboard({ tickets }: TicketDashboardProps) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<FilterStatus>('all');
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
  const [returnFocusTicketId, setReturnFocusTicketId] = useState<number | null>(null);

  // Normalize search query by trimming whitespace and converting to lowercase
  const normalizedQuery = query.trim().toLowerCase();

  // Combine title search and status filtering with AND condition
  const visibleTickets = tickets.filter((ticket) => {
    const matchesTitle = ticket.title.toLowerCase().includes(normalizedQuery);
    const matchesStatus = status === 'all' || ticket.status === status;
    return matchesTitle && matchesStatus;
  });

  const hasNoMatches = tickets.length > 0 && visibleTickets.length === 0;

  const handleClearFilters = () => {
    setQuery('');
    setStatus('all');
    setSelectedTicketId(null);
    setReturnFocusTicketId(null);
  };

  const selectedTicket =
    tickets.find((ticket) => ticket.ticketId === selectedTicketId) ?? null;

  return (
    <div>
      <div className="ticket-controls">
        <div className="ticket-search">
          <label htmlFor="ticket-search">Search tickets</label>
          <input
            id="ticket-search"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelectedTicketId(null);
              setReturnFocusTicketId(null);
            }}
          />
        </div>

        <div className="ticket-status-filter">
          <label htmlFor="ticket-status">Status</label>
          <select
            id="ticket-status"
            value={status}
            onChange={(event) => {
              const value = event.target.value;
              if (isFilterStatus(value)) {
                setStatus(value);
                setSelectedTicketId(null);
                setReturnFocusTicketId(null);
              }
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <button type="button" onClick={handleClearFilters}>
          Clear filters
        </button>
      </div>

      <p className="ticket-result-count">
        Showing {visibleTickets.length} of {tickets.length} tickets
      </p>

      {hasNoMatches ? (
        <p>No matching tickets.</p>
      ) : (
        <TicketTable
          tickets={visibleTickets}
          onSelectTicket={(ticketId) => {
            setReturnFocusTicketId(null);
            setSelectedTicketId(ticketId);
          }}
          focusTicketId={returnFocusTicketId}
          selectedTicketId={selectedTicketId}
        />
      )}

      {selectedTicket && (
        <TicketDetail
          ticket={selectedTicket}
          onClose={() => {
            setReturnFocusTicketId(selectedTicket.ticketId);
            setSelectedTicketId(null);
          }}
        />
      )}
    </div>
  );
}
