import {
  isId, isRecord, isPage, matchesPage, validPageQuery, pageParams, withQuery,
  invalidRequest, requestResource, type Page, type PageQuery, type ResourceResult,
} from './resources';

export type OrganizationRole = 'owner' | 'admin' | 'agent' | 'customer';
export type Organization = { organization_id: number; name: string; is_active: boolean };
export type OwnMembership = {
  membership_id: number; organization_id: number; role: OrganizationRole; is_active: boolean;
};
export type OrganizationContext = { organization: Organization; own_membership: OwnMembership };
export type OrganizationQuery = PageQuery & { is_active?: boolean };

export function isOrganization(value: unknown): value is Organization {
  return isRecord(value) && isId(value.organization_id) &&
    typeof value.name === 'string' && value.name.trim().length > 0 &&
    typeof value.is_active === 'boolean';
}

export function isOrganizationContext(value: unknown): value is OrganizationContext {
  if (!isRecord(value) || !isOrganization(value.organization) || !isRecord(value.own_membership)) return false;
  const membership = value.own_membership;
  return isId(membership.membership_id) && isId(membership.organization_id) &&
    membership.organization_id === value.organization.organization_id &&
    membership.is_active === true && typeof membership.role === 'string' &&
    ['owner', 'admin', 'agent', 'customer'].includes(membership.role);
}

export function isOrganizationPage(value: unknown): value is Page<OrganizationContext> {
  return isPage(value, isOrganizationContext) &&
    new Set(value.items.map(item => item.organization.organization_id)).size === value.items.length;
}

export function listOrganizations(
  token: string, query: OrganizationQuery = {}, signal?: AbortSignal,
): Promise<ResourceResult<Page<OrganizationContext>>> {
  if (!validPageQuery(query) || (query.is_active !== undefined && typeof query.is_active !== 'boolean')) {
    return Promise.resolve(invalidRequest());
  }
  const params = pageParams(query);
  if (query.is_active !== undefined) params.set('is_active', String(query.is_active));
  return requestResource(withQuery('/organizations', params), token,
    (value): value is Page<OrganizationContext> => isOrganizationPage(value) && matchesPage(value, query) &&
      value.items.every(item => query.is_active === undefined || item.organization.is_active === query.is_active),
    { signal });
}

export function getOrganization(token: string, organizationId: number, signal?: AbortSignal): Promise<ResourceResult<Organization>> {
  if (!isId(organizationId)) return Promise.resolve(invalidRequest());
  return requestResource(`/organizations/${organizationId}`, token,
    (value): value is Organization => isOrganization(value) && value.organization_id === organizationId, { signal });
}

export function createOrganization(token: string, input: { name: string }, signal?: AbortSignal): Promise<ResourceResult<OrganizationContext>> {
  // The backend remains the authority for exact Unicode name normalization.
  if (typeof input.name !== 'string') return Promise.resolve(invalidRequest());
  return requestResource('/organizations', token,
    (value): value is OrganizationContext => isOrganizationContext(value) &&
      value.organization.is_active && value.own_membership.role === 'owner',
    { signal, body: { name: input.name }, expectedStatus: 201 });
}
