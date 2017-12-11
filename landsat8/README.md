update imagery set priority=round((meta->'L1_METADATA_FILE'->'IMAGE_ATTRIBUTES'->>'CLOUD_COVER')::numeric) where meta->'L1_METADATA_FILE'->'IMAGE_ATTRIBUTES'->'CLOUD_COVER' is not null;
