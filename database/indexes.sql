BEGIN;

-- Deterministic organization resolution.
CREATE INDEX IF NOT EXISTS organizations_normalized_name_idx
    ON public.organizations (normalized_name);

CREATE INDEX IF NOT EXISTS organizations_search_key_idx
    ON public.organizations (search_key);

CREATE INDEX IF NOT EXISTS organizations_province_name_idx
    ON public.organizations (province_name);

CREATE INDEX IF NOT EXISTS organizations_type_code_idx
    ON public.organizations (organization_type_code);

CREATE INDEX IF NOT EXISTS organizations_management_idx
    ON public.organizations (management);

CREATE INDEX IF NOT EXISTS organizations_parent_id_idx
    ON public.organizations (parent_organization_id);

-- The current dataset has no search-key collision inside one province, making
-- this the most useful composite exact/disambiguation index for Version 1.
CREATE INDEX IF NOT EXISTS organizations_search_key_province_idx
    ON public.organizations (search_key, province_name);

CREATE INDEX IF NOT EXISTS organizations_province_type_idx
    ON public.organizations (province_name, organization_type_code);

-- Alias lookup is deterministic but an alias may intentionally point to more
-- than one organization, so these indexes are non-unique globally.
CREATE INDEX IF NOT EXISTS organization_aliases_normalized_alias_idx
    ON public.organization_aliases (normalized_alias);

CREATE INDEX IF NOT EXISTS organization_aliases_search_key_idx
    ON public.organization_aliases (alias_search_key);

CREATE INDEX IF NOT EXISTS organization_aliases_org_id_idx
    ON public.organization_aliases (organization_id);

-- Operational/audit queries for import failures and test evaluation.
CREATE INDEX IF NOT EXISTS staging_organizations_batch_status_idx
    ON public.staging_organizations (import_batch_id, validation_status);

CREATE INDEX IF NOT EXISTS staging_organizations_batch_org_id_idx
    ON public.staging_organizations (import_batch_id, organization_id);

CREATE INDEX IF NOT EXISTS matching_test_cases_split_scenario_idx
    ON public.matching_test_cases (dataset_split, scenario);

COMMIT;
