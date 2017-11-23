# # Explanation

from __future__ import absolute_import, print_function

import os
import uuid

from flask import Flask

from flask_celeryext import FlaskCeleryExt
from invenio_db import InvenioDB, db
from invenio_indexer import InvenioIndexer
from invenio_indexer.api import RecordIndexer
from invenio_pidstore import InvenioPIDStore
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import InvenioRecords, Record
from invenio_records_rest import InvenioRecordsREST
from invenio_records_rest.config import RECORDS_REST_ENDPOINTS
from invenio_records_rest.facets import terms_filter
from invenio_records_rest.utils import PIDConverter
from invenio_rest import InvenioREST
from invenio_search import InvenioSearch

# # Initialization

# Create a Flask application

# create application's instance directory. Needed for this example only.
current_dir = os.path.dirname(os.path.realpath(__file__))
instance_dir = os.path.join(current_dir, 'app_instance')
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)

index_name = 'testrecords-testrecord-v1.0.0'
app = Flask('myapp', instance_path=instance_dir)


# Since invenio-records-rest relies heavily in configuration
# we are going to set the minimal configuration.

# FIXME keep amount of configuration as small as possible.

app.config.update(
    CELERY_ALWAYS_EAGER=True,
    CELERY_CACHE_BACKEND='memory',
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_RESULT_BACKEND='cache',
    # No permission checking
    RECORDS_REST_DEFAULT_CREATE_PERMISSION_FACTORY=None,
    RECORDS_REST_DEFAULT_READ_PERMISSION_FACTORY=None,
    RECORDS_REST_DEFAULT_UPDATE_PERMISSION_FACTORY=None,
    RECORDS_REST_DEFAULT_DELETE_PERMISSION_FACTORY=None,
    SQLALCHEMY_TRACK_MODIFICATIONS=True,
    INDEXER_DEFAULT_INDEX=index_name,
    INDEXER_DEFAULT_DOC_TYPE='testrecord-v1.0.0',
    SQLALCHEMY_DATABASE_URI=os.getenv('SQLALCHEMY_DATABASE_URI',
                                      'sqlite:///app.db'),
)
app.config['RECORDS_REST_ENDPOINTS'] = RECORDS_REST_ENDPOINTS
app.config['RECORDS_REST_ENDPOINTS']['recid']['search_index'] = index_name
# Configure suggesters
app.config['RECORDS_REST_ENDPOINTS']['recid']['suggesters'] = {
    'title-complete': {
        'completion': {
            # see testrecord-v1.0.0.json for index configuration
            'field': 'suggest_title',
            'size': 10,
        }
    }
}
# Sort options
app.config['RECORDS_REST_SORT_OPTIONS'] = {
    index_name: {
        'title': dict(fields=['title'], title='Title', order=1),
        'control_number': dict(
            fields=['control_number'], title='Record identifier', order=1),
    }
}
# Default sorting.
app.config['RECORDS_REST_DEFAULT_SORT'] = {
    index_name: {
        'query': 'control_number',
        'noquery': '-control_number',
    }
}
# Aggregations and filtering
app.config['RECORDS_REST_FACETS'] = {
    index_name: {
        'aggs': {
            'type': {'terms': {'field': 'type'}}
        },
        'post_filters': {
            'type': terms_filter('type'),
        },
        'filters': {
            'typefilter': terms_filter('type'),
        }
    }
}
app.url_map.converters['pid'] = PIDConverter

# Initialize dependencies

FlaskCeleryExt(app)
ext_db = InvenioDB(app)
InvenioREST(app)
InvenioPIDStore(app)
InvenioRecords(app)
search = InvenioSearch(app)
search.register_mappings('testrecords', 'data')
InvenioIndexer(app)
InvenioRecordsREST(app)


# Initialize DB
# push Flask application context
app.app_context().push()
# Create database and tables
db.create_all()


# Demo data
# Record example 1
record_1 = Record.create({
    'title': 'Awesome meeting report',
    'description': 'Notes of the last meeting.',
    'participants': 42,
    'type': 'report',
}, id_=uuid.uuid4())

# Record example 2
record_2 = Record.create({
    'title': 'Furniture order',
    'description': 'Tables for the meeting room.',
    'type': 'order',
}, id_=uuid.uuid4())

db.session.commit()


# # Minting records, index initialization

indexer = RecordIndexer()
pid1 = PersistentIdentifier.create(
    'recid', '1', object_type='rec', object_uuid=record_1.id,
    status=PIDStatus.REGISTERED)

pid2 = PersistentIdentifier.create(
    'recid', '2', object_type='rec', object_uuid=record_2.id,
    status=PIDStatus.REGISTERED)

indexer.index_by_id(pid1.object_uuid)
indexer.index_by_id(pid2.object_uuid)
