import { useState } from 'react';
import type { TicketSummary } from '../types/ticket';
import TicketTable from './TicketTable';

type TicketDashboardProps = {
  tickets: TicketSummary[];
};

export default function TicketDashboard({ tickets }: TicketDashboardProps) {
  const [query, setQuery] = useState('');

  // Normalize search query by trimming leading/trailing whitespace and converting to lowercase
  const normalizedQuery = query.trim().toLowerCase();

  // Filter tickets whose title contains the normalized query
  const visibleTickets = tickets.filter((ticket) =>
    ticket.title.toLowerCase().includes(normalizedQuery)
  );

  const hasNoMatches = tickets.length > 0 && visibleTickets.length === 0;

  return (
    <div>
      <div className="ticket-search">
        <label htmlFor="ticket-search">Search tickets</label>
        <input
          id="ticket-search"
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
        />
      </div>

      {hasNoMatches ? (
        <p>No matching tickets.</p>
      ) : (
        <TicketTable tickets={visibleTickets} />
      )}
    </div>
  );
}
