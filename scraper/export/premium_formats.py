"""
Premium Export Formats.

Additional export formats for advanced use cases.
Premium feature - competitors charge for these formats.

Supported formats:
- Parquet (columnar format for big data)
- Avro (schema-based binary format)
- Feather (fast binary format for Pandas/Arrow)
- ORC (optimized row columnar)
- Protocol Buffers
- MessagePack
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class PremiumExporter:
    """Export scraped data in premium formats."""

    @staticmethod
    async def export_parquet(
        data: List[Dict[str, Any]],
        output_path: str,
        compression: str = 'snappy',
        schema: Optional[Dict] = None
    ) -> str:
        """
        Export to Apache Parquet format.

        Parquet is a columnar storage format optimized for analytics.
        10-100x smaller than CSV, 10-100x faster to query.

        Args:
            data: List of records
            output_path: Output file path
            compression: Compression codec (snappy, gzip, brotli, lz4, zstd)
            schema: Optional schema definition

        Returns:
            Output file path
        """
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Infer or use provided schema
        if schema:
            # Convert schema dict to PyArrow schema
            fields = []
            for name, dtype in schema.items():
                pa_type = {
                    'string': pa.string(),
                    'int': pa.int64(),
                    'float': pa.float64(),
                    'bool': pa.bool_(),
                    'timestamp': pa.timestamp('ns'),
                }[dtype]
                fields.append(pa.field(name, pa_type))

            pa_schema = pa.schema(fields)
            table = pa.Table.from_pandas(df, schema=pa_schema)
        else:
            table = pa.Table.from_pandas(df)

        # Write with compression
        pq.write_table(
            table,
            output_path,
            compression=compression,
            use_dictionary=True,  # Enable dictionary encoding
            write_statistics=True  # Enable column statistics
        )

        file_size = Path(output_path).stat().st_size
        logger.info(f"Exported {len(data)} records to Parquet: {output_path} ({file_size:,} bytes)")

        return output_path

    @staticmethod
    async def export_avro(
        data: List[Dict[str, Any]],
        output_path: str,
        schema: Optional[Dict] = None,
        codec: str = 'deflate'
    ) -> str:
        """
        Export to Apache Avro format.

        Avro is a binary format with embedded schema, ideal for data exchange.

        Args:
            data: List of records
            output_path: Output file path
            schema: Avro schema (auto-inferred if not provided)
            codec: Compression codec (null, deflate, snappy)

        Returns:
            Output file path
        """
        from fastavro import writer, parse_schema

        # Auto-generate schema if not provided
        if schema is None:
            schema = PremiumExporter._infer_avro_schema(data)

        parsed_schema = parse_schema(schema)

        # Write Avro file
        with open(output_path, 'wb') as out:
            writer(out, parsed_schema, data, codec=codec)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Exported {len(data)} records to Avro: {output_path} ({file_size:,} bytes)")

        return output_path

    @staticmethod
    def _infer_avro_schema(data: List[Dict[str, Any]]) -> Dict:
        """Infer Avro schema from data."""
        if not data:
            return {
                "type": "record",
                "name": "ScrapedData",
                "fields": []
            }

        sample = data[0]
        fields = []

        type_map = {
            int: "long",
            float: "double",
            bool: "boolean",
            str: "string",
        }

        for key, value in sample.items():
            avro_type = type_map.get(type(value), "string")

            # Make fields nullable
            field = {
                "name": key,
                "type": ["null", avro_type],
                "default": None
            }

            fields.append(field)

        return {
            "type": "record",
            "name": "ScrapedData",
            "namespace": "com.grandmascrape",
            "fields": fields
        }

    @staticmethod
    async def export_feather(
        data: List[Dict[str, Any]],
        output_path: str,
        compression: str = 'lz4'
    ) -> str:
        """
        Export to Apache Arrow Feather format.

        Feather is extremely fast for Pandas/Arrow interop.
        5-10x faster than Parquet for read/write.

        Args:
            data: List of records
            output_path: Output file path
            compression: Compression (uncompressed, lz4, zstd)

        Returns:
            Output file path
        """
        import pandas as pd

        df = pd.DataFrame(data)

        # Write Feather file (Arrow IPC format)
        df.to_feather(output_path, compression=compression)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Exported {len(data)} records to Feather: {output_path} ({file_size:,} bytes)")

        return output_path

    @staticmethod
    async def export_orc(
        data: List[Dict[str, Any]],
        output_path: str,
        compression: str = 'zlib'
    ) -> str:
        """
        Export to Apache ORC format.

        ORC (Optimized Row Columnar) is highly optimized for Hive/Spark.

        Args:
            data: List of records
            output_path: Output file path
            compression: Compression (none, zlib, snappy, lz4, zstd)

        Returns:
            Output file path
        """
        import pandas as pd
        import pyarrow as pa
        import pyarrow.orc as orc

        df = pd.DataFrame(data)
        table = pa.Table.from_pandas(df)

        # Write ORC file
        orc.write_table(table, output_path, compression=compression)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Exported {len(data)} records to ORC: {output_path} ({file_size:,} bytes)")

        return output_path

    @staticmethod
    async def export_msgpack(
        data: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """
        Export to MessagePack format.

        MessagePack is a fast binary format, 2-5x smaller than JSON.

        Args:
            data: List of records
            output_path: Output file path

        Returns:
            Output file path
        """
        import msgpack

        with open(output_path, 'wb') as f:
            msgpack.pack(data, f, use_bin_type=True)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Exported {len(data)} records to MessagePack: {output_path} ({file_size:,} bytes)")

        return output_path

    @staticmethod
    async def export_xml(
        data: List[Dict[str, Any]],
        output_path: str,
        root_name: str = "data",
        row_name: str = "item"
    ) -> str:
        """
        Export to XML format.

        Args:
            data: List of records
            output_path: Output file path
            root_name: Root element name
            row_name: Row element name

        Returns:
            Output file path
        """
        import xml.etree.ElementTree as ET

        root = ET.Element(root_name)

        for record in data:
            item = ET.SubElement(root, row_name)

            for key, value in record.items():
                field = ET.SubElement(item, key)
                field.text = str(value) if value is not None else ""

        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Exported {len(data)} records to XML: {output_path} ({file_size:,} bytes)")

        return output_path

    @staticmethod
    async def export_ndjson(
        data: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """
        Export to Newline-Delimited JSON (NDJSON).

        Perfect for streaming and log data.

        Args:
            data: List of records
            output_path: Output file path

        Returns:
            Output file path
        """
        with open(output_path, 'w') as f:
            for record in data:
                f.write(json.dumps(record) + '\n')

        file_size = Path(output_path).stat().st_size
        logger.info(f"Exported {len(data)} records to NDJSON: {output_path} ({file_size:,} bytes)")

        return output_path


# ============================================================================
# FORMAT COMPARISON
# ============================================================================

class FormatComparison:
    """
    Compare different export formats for performance and size.

    Helps users choose the best format for their use case.
    """

    @staticmethod
    async def benchmark_formats(
        data: List[Dict[str, Any]],
        output_dir: str = '/tmp'
    ) -> Dict[str, Dict[str, Any]]:
        """
        Benchmark all formats and return comparison.

        Returns:
            Dict with format stats (size, write time, compression ratio)
        """
        import time

        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        results = {}

        # Test all formats
        formats = [
            ('CSV', 'csv'),
            ('JSON', 'json'),
            ('Parquet', 'parquet'),
            ('Avro', 'avro'),
            ('Feather', 'feather'),
            ('ORC', 'orc'),
            ('MessagePack', 'msgpack'),
            ('NDJSON', 'ndjson'),
        ]

        for name, ext in formats:
            output_path = output_dir / f"benchmark.{ext}"

            start_time = time.time()

            try:
                if name == 'CSV':
                    import pandas as pd
                    pd.DataFrame(data).to_csv(output_path, index=False)
                elif name == 'JSON':
                    with open(output_path, 'w') as f:
                        json.dump(data, f)
                elif name == 'Parquet':
                    await PremiumExporter.export_parquet(data, str(output_path))
                elif name == 'Avro':
                    await PremiumExporter.export_avro(data, str(output_path))
                elif name == 'Feather':
                    await PremiumExporter.export_feather(data, str(output_path))
                elif name == 'ORC':
                    await PremiumExporter.export_orc(data, str(output_path))
                elif name == 'MessagePack':
                    await PremiumExporter.export_msgpack(data, str(output_path))
                elif name == 'NDJSON':
                    await PremiumExporter.export_ndjson(data, str(output_path))

                write_time = time.time() - start_time
                file_size = output_path.stat().st_size

                # Calculate compression ratio vs JSON
                json_path = output_dir / "benchmark.json"
                if json_path.exists():
                    json_size = json_path.stat().st_size
                    compression_ratio = file_size / json_size
                else:
                    compression_ratio = 1.0

                results[name] = {
                    'size_bytes': file_size,
                    'size_mb': file_size / 1024 / 1024,
                    'write_time_ms': write_time * 1000,
                    'compression_ratio': compression_ratio,
                    'size_vs_json': f"{compression_ratio:.1%}"
                }

            except Exception as e:
                logger.warning(f"Failed to benchmark {name}: {e}")
                results[name] = {'error': str(e)}

        return results


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of using premium export formats."""

    # Sample data
    data = [
        {'id': 1, 'name': 'Product A', 'price': 19.99, 'in_stock': True},
        {'id': 2, 'name': 'Product B', 'price': 29.99, 'in_stock': False},
        {'id': 3, 'name': 'Product C', 'price': 39.99, 'in_stock': True},
    ] * 1000  # 3000 records

    # Export to Parquet (best for analytics)
    await PremiumExporter.export_parquet(
        data,
        'output.parquet',
        compression='zstd'  # Best compression
    )

    # Export to Avro (best for data exchange)
    await PremiumExporter.export_avro(
        data,
        'output.avro',
        codec='snappy'  # Fast compression
    )

    # Export to Feather (best for Pandas)
    await PremiumExporter.export_feather(
        data,
        'output.feather',
        compression='lz4'  # Fastest
    )

    # Benchmark all formats
    benchmark = FormatComparison()
    results = await benchmark.benchmark_formats(data)

    print("\nFormat Comparison:")
    print("-" * 80)
    for format_name, stats in results.items():
        if 'error' in stats:
            print(f"{format_name:15} - Error: {stats['error']}")
        else:
            print(f"{format_name:15} - {stats['size_mb']:.2f} MB, "
                  f"{stats['write_time_ms']:.1f}ms, "
                  f"{stats['size_vs_json']} of JSON size")
