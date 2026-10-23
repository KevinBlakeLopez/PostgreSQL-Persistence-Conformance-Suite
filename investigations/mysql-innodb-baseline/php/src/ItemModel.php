<?php

declare(strict_types=1);

namespace App\Models;

use CodeIgniter\Model;

class ItemModel extends Model
{
    protected $table = 'item';
    protected $primaryKey = 'id';
    protected $returnType = 'array';
    protected $allowedFields = ['label'];
    protected $useTimestamps = false;
    protected $skipValidation = true;
    protected $allowCallbacks = false;
}
