National Agriculture Imagery Program (NAIP) imagery is available on Amazon S3 in a requester-pays bucket.

Listing is not enabled on this bucket, so `manifest.txt` must be fetched in order to effect such functionality:

```bash
aws s3api get-object --bucket aws-naip --key manifest.txt --request-payer requester manifest.txt
```

Files are organized according to the following convention:

```
{state}/{year}/{resolution}/{prefix}/{quadrangle}/m_{quadrangle}{suffix}_{quadrant}_{version}_{date}.tif
```

4-band (RGB + IR) images are available but are not processed appropriately for on-the-fly rendering.

Shapefiles are available with information on the areas that they cover, e.g.:

```
al/2013/1m/shpfl/naip_3_13_2_1_al.dbf
al/2013/1m/shpfl/naip_3_13_2_1_al.sbn
al/2013/1m/shpfl/naip_3_13_2_1_al.sbx
al/2013/1m/shpfl/naip_3_13_2_1_al.shp
al/2013/1m/shpfl/naip_3_13_2_1_al.shp.xml
al/2013/1m/shpfl/naip_3_13_2_1_al.shx
```

If `.prj`s are not available, it's safe to assume that these are in EPSG:4269.


```sql
update imagery set acquired_at = (meta->>'SrcImgDate')::timestamp with time zone where meta->'SrcImgDate' is not null;
update imagery set acquired_at = (meta->>'naip_3_136')::timestamp with time zone where meta->'naip_3_136' is not null;
```
