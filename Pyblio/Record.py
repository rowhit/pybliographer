# This file is part of pybliographer
# 
# Copyright (C) 2003, Peter Schulte-Stracke
# Email : peter.schulte-stracke@t-online.de
# 	   
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2 
# of the License, or (at your option) any later version.
#   
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details. 
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# 
# $Id$

"""

      ##################################################
      #                                                #
      #           E X P E R I M E N T A L              #
      #                                                #
      ##################################################

      Record -- database record, abstract class
      Recordset -- a set of records, abstract class
      Iterator -- an iterator over a record set, abstract class
      Index -- an index, abstract class

  Functions:
      register -- a subclass of Record
      create -- an instance of a subclass of Record


Common Recordset methods 

add        a potentially new reocrd
extend     a recordset by adding all of another recordset
remove     a record (or folder)
delete     a record from the database

index      ?

sort       returns a new RS ?
flatten

insert     a sub folder

len        number of items in RS, index
count      number of items with attribute, number of children





"""
from __future__ import generators
import copy

#     Constants
#--------------------------------------------------

BIBLI = ord('B')
OLDPY = ord('O')
PERSO = ord('P')


MARKED =     1 << 12
TEMPORARY =  1 << 13
DIRTY =      1 << 14
DELETED =    1 << 15

#     Record         (Storage Object) 
#--------------------------------------------------

class Record:

    """A database record..

    DB_ID       is the unique object identifier
    DB          the database
    _flg        comprises (binary) flags


   """
    Typ = 0
    DB_ID = None
    DB = None
    _flg = 0

    def __init__ (self, 
                  dbid=None, db=None,
                  *args, **argh):
        
        if db and dbid:
            self.load (db, dbid)
            
        self.sets = []
        

    def delete (self, purge=0):
        """Delete record.  Move it into the deleted
        folder, and mark it logically deleted.
        """
        self.set_folder(4) #### Folder.Deleted
        self._flg  |= DELETED

    def is_deleted (self):
        """Test if this record is already marked deleted."""
        return self._flg & DELETED
    
    def purge (self):
        """Remove it from all sets etc. and physically remove
        it from the database."""
        for i in self.sets:
            self.del_folder (i)
        self.DB.remove(self.DB_ID)
        
    def index_set (self):
        """Returns a list of index entries for this record."""
        return self.common_index_set()

    def common_index_set(self):
        """Returns a list of common index entries for this record."""
        return []
    
    def load (self, db, db_id):
        self.DB_ID = dbid
        self.DB = db
        db.load(self, db_id)

    def save (self):
        db.save (db_id)
        self._flg &= ~ DIRTY
    
    # Lists, attributes
    # --------------------------------------------------

    def set_mark (self):
        """Set a simple, global, mark."""
        self._flg |= MARKED
        self.set_folder (1)

    def del_mark (self):
        """Removes a simple, global, mark."""
        self._flg &= not MARKED
        self.del_folder (1)

    def is_marked (self):
        """Test for a simple, global, mark."""
        return self._flg & MARKED
    
    # Note: the number of sets an item is member of is
    # presumed to be small, thus is seems sufficient to use
    # a simple sequence to keep track of it.
    
    def set_folder (self, folder):
        """This record joins a folder """
        f = self.DB.get_folder (folder)
        if not f in f.sets:
            f.sets.append(f)
            f.add(self)

    def del_folder (self, folder):
        """This record leaves a folder """
        f = self.DB.get_folder (folder)
        if f.Id in f.sets:
            f.sets.remove(f.Id)
            f.remove(self)
    
#
#     Record Factory 
#--------------------------------------------------

_register = {}

def register (subclass, *args, **argh):
    """Registers a subclass of Record.  If positional args
    are given, they are prefixed to the __init__ call,
    i.e. currying it. Any keyword arguments are merged upon
    calling __init__, effectively acting as defaults."""
    global _register
    tag = subclass.Typ
    _register[tag] = (subclass, args, argh)
    print 'REGISTER:', subclass.Typ, args, argh

def create (tag, *args1, **argh1):
    """Create an instance of the subclass registered with the tag."""
    
    k, args, argh = _register[tag]
    args += args1
    argh.update(argh1)
    print 'CREATE:', k, args, argh
    return k (*args, **argh)


Dummy = Record()
Dummy._flg = -1 #DIRTY | MARKED | TEMPORARY | DELETED
Dummy.DB_ID = -1

#
#     RecordSet       
#--------------------------------------------------

class RecordSet:

    """This class represents a set of items (of various kinds)
    either selected from a database or currently being entered
    or imported. Thus it is the result of Open, of Query, of
    data entry, etc.

    It gives the ability to specify  display style (?),
    position or similar preferences.

    Acts also as an interface between database and consumers/
    suppliers. 

    The standard recordset just acts as a set (enumeration) of records.

    Iteration: the iterator method reutrns an iterator for this recordset.

    A recordset has a database or is itself a database. 

    """
    _Typ  = 'r'
    default_filter = None
    default_sorting = None
    default_style = None
    default_position = None
    low_limit = None
    high_limit = None

    def __init__ (self, base,  control=None, 
                 name= 'A Record Set', temporary = 0,*args, **argh):
        """
        base is the database which contains the record
        """
        self.base = base
        self.name = name 
        #self.control = control or Coco.RecordSet()
        self.order = None ## ??
        self.temporary = temporary
        self._items = {}
        print 'RECORDSET BASE:', `self.base`
        self.base.register_recordset(self)
        return

    def __len__ (self):
        return len(self._items)

    def __del__ (self):
        self.base.unregister(self)
        self.clear()
        
    def get (self, db_id):
        """Retrieve a record from the database.
        NOTE: Overridden by the db subclass."""
        return self.base.get(db_id)
    
    def clear(self):
        for i in self._items:
            self.remove(i)
    
    #--------------------------------------------------
    #   Input interface

    def add (self, record, position=-1):
        """Add a record to the base, if necessary.
        This must go through the base add method, because in
        typical situations, both, the data base and the current
        result set are meant to be updated.

        Only items (not ids) are possible inputs.????
        NOTE that in a database implementation, much must be added;
        here it suffices to delegate.
        NOTE that a.t.m. we do not keep the sequence!
        NOTE that we should perhaps accept Ids as well
        """

        if not self.check_in(record):
            return
        
        if record.DB:
            assert record.DB == self.base, 'ERROR: wrong database'
            if self._items.has_key(record.DB_ID):
                return record
        else:
            assert record.DB_ID == None, 'ERROR: record not new'
            record = self.base.add(record) 
        self._items [record.DB_ID] = record
        return record

    def extend (self, set):
        """Extend a recordset by adding all items from another
        recordset. Does not change the other recordset"""
        for item in set:
            self.copy(item)

    def insert (self, item, position=-1):
        """Only used for Folders: insert a folder hierarchically. """
        raise NotImplementedError
    
    def remove (self, record):
        """Remove a record from this recordset"""
        if self.check_out(record):
            del self._items[record.DB_ID]
        
    def check_in (self,record):
        return True
    
    def check_out (self, record):
        return True

    def move (self, record, set):
        """Move a record *from* one recordset set into this one.
        Note that the order of arguments 
        is uncommon: target.move(item, from) """
        self.copy(record, set)
        set.remove (record)

    def copy (self, record, set=None):
        """Copy a record (from set) into this recordset."""
        if record.DB != self.base:
            record = copy.copy(record)
            record.DB = None
            record.DB_ID = None
        return self.add(record)

    #--------------------------------------------------
    #   Defaults
   
    def set_filter(self, filter):
        """Set the filter of the Recordset."""
        self.default_filter = filter
        #self.control['filter'] = filter
        return
    
    def set_sorting (self, sorting):
        """set the sorting order for the Recordset."""
        self.default_sorting = sorting
        #self.control['sorting'] = sorting
        return

    def set_style (self, style):
        self.default_style = style
        #self.control['style'] = style
        return

    def set_order (self, kind):
        """Selects the kind of ordering required. Typical values are:
        0  implicit,  
        1  author only,
        2  title only
        3  author/title style.
        """

        if self.order:
            self.order = kind
            #self.redisplay()
        else:
            self.order = kind
        return

    def set_position(self, position):
        """Sets the starting position for the iterator.
        0 means the very  first record, acording to current ordering,
        -1 means the very last one."""
        
        self.default_position = position
        
    def set_limit (self, start, stop=None):
        if stop != None:
            self.low_limit = start
            self.high_limit = stop
        else:
            self.low_limit = None
            self.high_limit = stop
        return

    #--------------------------------------------------
    #   Utilities
    
    def create_bibtex_key(self, item, dict, url):
        from Pyblio import Autoload, Config, Key
        if item.key is None:
            # call a key generator
            keytype   = Config.get ('base/keyformat').data
            return  Autoload.get_by_name (
                'key', keytype).data (item, dict)
        else:
            prefix = item.key.key
            key = Key.Key (self, prefix)
            suffix = ord ('a')
            while dict.has_key (key):
                key = Key.Key (self, prefix + '-' + chr (suffix))
                suffix = suffix + 1
            return key
    
    

#
#     Index       ()
#--------------------------------------------------

class Index (RecordSet):
    """Abstract base class for Indexes.

    An index has a Base, which is a database. 

    An index basically associates a Key with one or more Items;
    conversely, one item is usually associated with a number of
    keys.

    As a rule, an index is concerned with a certain concept, like
    authorship, and its generalisations.  In order to reduce the
    number of index files, however, multiple indexes are folded
    into one file, and accordingly distinguished.

    Because some indexes produce a large number of redundant or
    irrelevent results, a masking facility allows to restrict
    retrieval to only a subset of records.
      
    """

    def __init__ (self, base, name, title='', *args, **argh):

        """Create an Index.
        base -- database instance
        name -- string identifying index
        title -- string for user communication
        """
        RecordSet.__init__(self, base, name='Index %s' %(name))
        self.title = title or name
        self.connect (base, name , *args, **argh)
     
        self.size = 100
        return

    def __str__(self):
        return '<Index: %s>' %(self.title)

    def __len__ (self):
        ## number of records: stat()['ndata'] (nkeys ?)
        return self.size

    #--------------------------------------------------
    #   Database interface
    #
    # note that this may require additions to handle
    # subindices and masks
    #   
    #   
    # The implementation uses the following interface:
    #   put_x (self, key, db_id)
    #   get_x (self, key) => list of db_id
    #   del_x (self, key, db_id)

    def add_x (self, db_id, keys):
        """Associates db_id with keys """
        try:
            for k in keys:
                self.put_x(k, db_id)
        except TypeError:
            self.put_x (keys, db_id)

    def remove_x (self, db_id, keys):
        try:
            for k in keys:
                self.del_x (k, db_id)
        except TypeError:
            self.del_x (keys, db_id)

    def find (self, key):
        """Search for first record greater or equal
        in key sequence."""
        pass
    
    def connect (self, base, name , *args, **argh):
        """Connect the Index with the database.   """
        r = base.connectx (name,  *args, **argh)
        return
 
        
        
#
#     Iterator       ()
#--------------------------------------------------

class Iterator:

    def __init__ (self, base, title='an iterator')
    self.title = title
    self.base  = base.base

    
    def __iter__ (self): return self

    def next (self):
        return self.db.get(self.nextid())

    def nextid (self):
        

    pass


    

# Local Variables:
# py-master-file: "tRecord.py"
# End: