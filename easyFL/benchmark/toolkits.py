"""
DISTRIBUTION OF DATASET
-----------------------------------------------------------------------------------
balance:
    iid:            0 : identical and independent distributions of the dataset among clients
    label skew:     1 Quantity:  each party owns data samples of a fixed number of labels.
                    2 Dirichlet: each party is allocated a proportion of the samples of each label according to Dirichlet distribution.
                    3 Shard: each party is allocated the same numbers of shards that is sorted by the labels of the data
-----------------------------------------------------------------------------------
depends on partitions:
    feature skew:   4 Noise: each party owns data samples of a fixed number of labels.
                    5 ID: For Shakespeare\FEMNIST, we divide and assign the writers (and their characters) into each party randomly and equally.
-----------------------------------------------------------------------------------
imbalance:
    iid:            6 Vol: only the vol of local dataset varies.
    niid:           7 Vol: for generating synthetic_classification data
"""

import ujson
import shutil
import numpy as np
import os.path
import random
import os
import ssl
from torch.utils.data import Dataset, DataLoader
import torch
ssl._create_default_https_context = ssl._create_unverified_context
import importlib
import collections
from torchvision import datasets, transforms

# ========================================Task Generator============================================
# This part is for generating federated dataset from original dataset. The generation process should be
# implemented in the method run(). Here we provide a basic class BasicTaskGen as a standard process to
# generate federated dataset, which mainly includes:
#   1) loading and pre-processing data by load_data(),
#   2) partitioning dataset by partition(),
#   3) saving the partitioned dataset for clients and test dataset for server as the final fedtask by save_data().
# We also provide a default task generator DefaultTaskGen to cover the generating of several datasets (e.g. MNIST,
# CIFAR10, CIFAR100, FashionMNIST, EMNIST)， which enables joining different datasets with very few code (please see
# the core.py at the path of these datasets for details).
class BasicTaskGen:
    _TYPE_DIST = {
        0: 'iid',
        1: 'label_skew_quantity',
        2: 'label_skew_dirichlet',
        3: 'label_skew_shard',
        4: 'feature_skew_noise',
        5: 'feature_skew_id',
        6: 'iid_volumn_skew',
        7: 'niid_volumn_skew',
        8: 'concept skew',
        9: 'concept and feature skew and balance',
        10: 'concept and feature skew and imbalance',
    }
    _TYPE_DATASET = ['2DImage', '3DImage', 'Text', 'Sequential', 'Graph', 'Tabular']

    def __init__(self, benchmark, dist_id, skewness, rawdata_path, seed=0):
        self.benchmark = benchmark
        self.task_rootpath = './fedtask'
        self.rawdata_path = rawdata_path
        self.dist_id = dist_id
        self.dist_name = self._TYPE_DIST[dist_id]
        self.skewness = 0 if dist_id==0 else skewness
        self.num_clients = -1
        self.seed = seed
        self.set_random_seed(self.seed)

    def run(self):
        """The whole process to generate federated task. """
        pass

    def load_data(self):
        """Download and load dataset into memory."""
        pass

    def partition(self):
        """Partition the data according to 'dist' and 'skewness'"""
        pass

    def save_data(self):
        """Save the federated dataset to the task_path/data.
        This algorithm should be implemented as the way to read
        data from disk that is defined by DataReader.read_data()
        """
        pass

    def save_info(self):
        """Save the task infomation to the .json file stored in taskpath"""
        pass

    def get_taskname(self):
        """Create task name and return it."""
        taskname = '_'.join([self.benchmark, 'cnum' +  str(self.num_clients), 'dist' + str(self.dist_id), 'skew' + str(self.skewness).replace(" ", ""), 'seed'+str(self.seed)])
        return taskname

    def get_client_names(self):
        k = str(len(str(self.num_clients)))
        return [('Client{:0>' + k + 'd}').format(i) for i in range(self.num_clients)]

    def create_task_directories(self):
        """Create the directories of the task."""
        taskname = self.get_taskname()
        taskpath = os.path.join(self.task_rootpath, taskname)
        os.mkdir(taskpath)
        os.mkdir(os.path.join(taskpath, 'record'))

    def _check_task_exist(self):
        """Check whether the task already exists."""
        taskname = self.get_taskname()
        return os.path.exists(os.path.join(self.task_rootpath, taskname))

    def set_random_seed(self,seed=0):
        """Set random seed"""
        random.seed(3 + seed)
        np.random.seed(97 + seed)
        os.environ['PYTHONHASHSEED'] = str(seed)

    def _remove_task(self):
        "remove the task when generating failed"
        if self._check_task_exist():
            taskname = self.get_taskname()
            taskpath = os.path.join(self.task_rootpath, taskname)
            shutil.rmtree(taskpath)
        return

class DefaultTaskGen(BasicTaskGen):
    def __init__(self, benchmark, dist_id, skewness, rawdata_path, num_clients=1, minvol=10, seed=0):
        super(DefaultTaskGen, self).__init__(benchmark, dist_id, skewness, rawdata_path, seed)
        self.minvol=minvol
        self.num_classes = -1
        self.train_data = None
        self.test_data = None
        self.num_clients = num_clients
        self.cnames = self.get_client_names()
        self.taskname = self.get_taskname()
        self.taskpath = os.path.join(self.task_rootpath, self.taskname)
        self.visualize = None
        self.save_data = self.XYData_to_json
        self.datasrc = {
            'lib': None,
            'class_name': None,
            'train_args': {},
            'test_args': {},
        }

    def run(self):
        """ Generate federated task"""
        # check if the task exists
        if self._check_task_exist():
            print("Task Already Exists.")
            return
        # read raw_data into self.train_data and self.test_data
        print('-----------------------------------------------------')
        print('Loading...')
        self.load_data()
        print('Done.')
        # partition data and hold-out for each local dataset
        print('-----------------------------------------------------')
        print('Partitioning data...')
        local_datas = self.partition()
        train_cidxs, valid_cidxs = self.local_holdout(local_datas, rate=0.8, shuffle=True)
        print('Done.')
        # save task infomation as .json file and the federated dataset
        print('-----------------------------------------------------')
        print('Saving data...')
        try:
            # create the directory of the task
            self.create_task_directories()
            # visualizing partition
            if self.visualize is not None:
                self.visualize(train_cidxs)
            self.save_data(train_cidxs, valid_cidxs)
        except:
            self._remove_task()
            print("Failed to saving splited dataset.")
        print('Done.')
        return

    def load_data(self):
        """ load and pre-process the raw data"""
        return

    def partition(self):
        # Partition self.train_data according to the delimiter and return indexes of data owned by each client as [c1data_idxs, ...] where the type of each element is list(int)
        if self.dist_id == 0:
            """IID"""
            d_idxs = np.random.permutation(len(self.train_data))
            local_datas = np.array_split(d_idxs, self.num_clients)
            local_datas = [data_idx.tolist() for data_idx in local_datas]

        elif self.dist_id == 1:
            """label_skew_quantity"""
            self.skewness = min(max(0, self.skewness),1.0)
            dpairs = [[did, self.train_data[did][-1]] for did in range(len(self.train_data))]
            num = max(int((1-self.skewness)*self.num_classes), 1)
            K = self.num_classes
            local_datas = [[] for _ in range(self.num_clients)]
            if num == K:
                for k in range(K):
                    idx_k = [p[0] for p in dpairs if p[1]==k]
                    np.random.shuffle(idx_k)
                    split = np.array_split(idx_k, self.num_clients)
                    for cid in range(self.num_clients):
                        local_datas[cid].extend(split[cid].tolist())
            else:
                times = [0 for _ in range(self.num_classes)]
                contain = []
                for i in range(self.num_clients):
                    current = [i % K]
                    times[i % K] += 1
                    j = 1
                    while (j < num):
                        ind = random.randint(0, K - 1)
                        if (ind not in current):
                            j = j + 1
                            current.append(ind)
                            times[ind] += 1
                    contain.append(current)
                for k in range(K):
                    idx_k = [p[0] for p in dpairs if p[1]==k]
                    np.random.shuffle(idx_k)
                    split = np.array_split(idx_k, times[k])
                    ids = 0
                    for cid in range(self.num_clients):
                        if k in contain[cid]:
                            local_datas[cid].extend(split[ids].tolist())
                            ids += 1

        elif self.dist_id == 2:
            """label_skew_dirichlet"""
            """alpha = (-4log(skewness + epsilon))**4"""
            MIN_ALPHA = 0.01
            alpha = (-4*np.log(self.skewness + 10e-8))**4
            alpha = max(alpha, MIN_ALPHA)
            labels = [self.train_data[did][-1] for did in range(len(self.train_data))]
            lb_counter = collections.Counter(labels)
            p = np.array([1.0*v/len(self.train_data) for v in lb_counter.values()])
            lb_dict = {}
            labels = np.array(labels)
            for lb in range(len(lb_counter.keys())):
                lb_dict[lb] = np.where(labels==lb)[0]
            proportions = [np.random.dirichlet(alpha*p) for _ in range(self.num_clients)]
            while np.any(np.isnan(proportions)):
                proportions = [np.random.dirichlet(alpha * p) for _ in range(self.num_clients)]
            while True:
                # generate dirichlet distribution till ||E(proportion) - P(D)||<=1e-5*self.num_classes
                mean_prop = np.mean(proportions, axis=0)
                error_norm = ((mean_prop-p)**2).sum()
                print("Error: {:.8f}".format(error_norm))
                if error_norm<=1e-3/self.num_classes:
                    break
                exclude_norms = []
                for cid in range(self.num_clients):
                    mean_excid = (mean_prop*self.num_clients-proportions[cid])/(self.num_clients-1)
                    error_excid = ((mean_excid-p)**2).sum()
                    exclude_norms.append(error_excid)
                excid = np.argmin(exclude_norms)
                sup_prop = [np.random.dirichlet(alpha*p) for _ in range(self.num_clients)]
                alter_norms = []
                for cid in range(self.num_clients):
                    if np.any(np.isnan(sup_prop[cid])):
                        continue
                    mean_alter_cid = mean_prop - proportions[excid]/self.num_clients + sup_prop[cid]/self.num_clients
                    error_alter = ((mean_alter_cid-p)**2).sum()
                    alter_norms.append(error_alter)
                if len(alter_norms)>0:
                    alcid = np.argmin(alter_norms)
                    proportions[excid] = sup_prop[alcid]
            local_datas = [[] for _ in range(self.num_clients)]
            self.dirichlet_dist = [] # for efficiently visualizing
            for lb in lb_counter.keys():
                lb_idxs = lb_dict[lb]
                lb_proportion = np.array([pi[lb] for pi in proportions])
                lb_proportion = lb_proportion/lb_proportion.sum()
                lb_proportion = (np.cumsum(lb_proportion) * len(lb_idxs)).astype(int)[:-1]
                lb_datas = np.split(lb_idxs, lb_proportion)
                self.dirichlet_dist.append([len(lb_data) for lb_data in lb_datas])
                local_datas = [local_data+lb_data.tolist() for local_data,lb_data in zip(local_datas, lb_datas)]
            self.dirichlet_dist = np.array(self.dirichlet_dist).T
            for i in range(self.num_clients):
                np.random.shuffle(local_datas[i])

        elif self.dist_id == 3:
            """label_skew_shard"""
            dpairs = [[did, self.train_data[did][-1]] for did in range(len(self.train_data))]
            self.skewness = min(max(0, self.skewness), 1.0)
            num_shards = max(int((1 - self.skewness) * self.num_classes * 2), 1)
            client_datasize = int(len(self.train_data) / self.num_clients)
            all_idxs = [i for i in range(len(self.train_data))]
            z = zip([p[1] for p in dpairs], all_idxs)
            z = sorted(z)
            labels, all_idxs = zip(*z)
            shardsize = int(client_datasize / num_shards)
            idxs_shard = range(int(self.num_clients * num_shards))
            local_datas = [[] for i in range(self.num_clients)]
            for i in range(self.num_clients):
                rand_set = set(np.random.choice(idxs_shard, num_shards, replace=False))
                idxs_shard = list(set(idxs_shard) - rand_set)
                for rand in rand_set:
                    local_datas[i].extend(all_idxs[rand * shardsize:(rand + 1) * shardsize])

        elif self.dist_id == 4:
            pass

        elif self.dist_id == 5:
            """feature_skew_id"""
            if not isinstance(self.train_data, TupleDataset):
                raise RuntimeError("Support for dist_id=5 only after setting the type of self.train_data is TupleDataset")
            Xs, IDs, Ys = self.train_data.tolist()
            self.num_clients = len(set(IDs))
            local_datas = [[] for _ in range(self.num_clients)]
            for did in range(len(IDs)):
                local_datas[IDs[did]].append(did)

        elif self.dist_id == 6:
            minv = 0
            d_idxs = np.random.permutation(len(self.train_data))
            while minv < self.minvol:
                proportions = np.random.dirichlet(np.repeat(self.skewness, self.num_clients))
                proportions = proportions / proportions.sum()
                minv = np.min(proportions * len(self.train_data))
            proportions = (np.cumsum(proportions) * len(d_idxs)).astype(int)[:-1]
            local_datas  = np.split(d_idxs, proportions)
        return local_datas

    def local_holdout(self, local_datas, rate=0.8, shuffle=False):
        """split each local dataset into train data and valid data according the rate."""
        train_cidxs = []
        valid_cidxs = []
        for local_data in local_datas:
            if shuffle:
                np.random.shuffle(local_data)
            k = int(len(local_data) * rate)
            train_cidxs.append(local_data[:k])
            valid_cidxs.append(local_data[k:])
        return train_cidxs, valid_cidxs


    def convert_data_for_saving(self):
        """Convert self.train_data and self.test_data to list that can be stored as .json file and the converted dataset={'x':[], 'y':[]}"""
        pass

    def XYData_to_json(self, train_cidxs, valid_cidxs):
        self.convert_data_for_saving()
        # save federated dataset
        feddata = {
            'store': 'XY',
            'client_names': self.cnames,
            'dtest': self.test_data

        }
        for cid in range(self.num_clients):
            feddata[self.cnames[cid]] = {
                'dtrain':{
                    'x':[self.train_data['x'][did] for did in train_cidxs[cid]], 'y':[self.train_data['y'][did] for did in train_cidxs[cid]]
                },
                'dvalid':{
                    'x':[self.train_data['x'][did] for did in valid_cidxs[cid]], 'y':[self.train_data['y'][did] for did in valid_cidxs[cid]]
                }
            }
        with open(os.path.join(self.taskpath, 'data.json'), 'w') as outf:
            ujson.dump(feddata, outf)
        return

    def IDXData_to_json(self, train_cidxs, valid_cidxs):
        if self.datasrc ==None:
            raise RuntimeError("Attr datasrc not Found. Please define it in __init__() before calling IndexData_to_json")
        feddata = {
            'store': 'IDX',
            'client_names': self.cnames,
            'dtest': [i for i in range(len(self.test_data))],
            'datasrc': self.datasrc
        }
        for cid in range(self.num_clients):
            feddata[self.cnames[cid]] = {
                'dtrain': list(train_cidxs[cid]),
                'dvalid': list(valid_cidxs[cid])
            }
        with open(os.path.join(self.taskpath, 'data.json'), 'w') as outf:
            print("yo")
            with open('yolo.txt', 'w') as fd:
                fd.write(str(feddata))

            #vvv = {'store': 'IDX', 'client_names': ['Client0', 'Client1', 'Client2', 'Client3', 'Client4'], 'dtest': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 350, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424, 425, 426, 427, 428, 429, 430, 431, 432, 433, 434, 435, 436, 437, 438, 439, 440, 441, 442, 443, 444, 445, 446, 447, 448, 449, 450, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 461, 462, 463, 464, 465, 466, 467, 468, 469, 470, 471, 472, 473, 474, 475, 476, 477, 478, 479, 480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493, 494, 495, 496, 497, 498, 499, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532, 533, 534, 535, 536, 537, 538, 539, 540, 541, 542, 543, 544, 545, 546, 547, 548, 549, 550, 551, 552, 553, 554, 555, 556, 557, 558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568, 569, 570, 571, 572, 573, 574, 575, 576, 577, 578, 579, 580, 581, 582, 583, 584, 585, 586, 587, 588, 589, 590, 591, 592, 593, 594, 595, 596, 597, 598, 599, 600, 601, 602, 603, 604, 605, 606, 607, 608, 609, 610, 611, 612, 613, 614, 615, 616, 617, 618, 619, 620, 621, 622, 623], 'datasrc': {'class_path': 'torchvision.datasets', 'class_name': 'ImageFolder', 'train_args': {'root': '"./benchmark/mine/pneumonia/train"', 'transform': 'transforms.Compose([transforms.ToTensor()])'}, 'test_args': {'root': '"./benchmark/mine/pneumonia/test"', 'transform': 'transforms.Compose([transforms.ToTensor()])'}}, 'Client0': {'dtrain': [964, 4432, 3835, 175, 1586, 4899, 709, 1132, 388, 2687, 3273, 1162, 3518, 4701, 471, 2570, 707, 2549, 1369, 4241, 2663, 3247, 1848, 1796, 2604, 4966, 5050, 2628, 4098, 317, 4661, 1992, 3298, 4991, 2755, 5188, 2006, 5135, 4817, 682, 1000, 2089, 999, 5019, 4355, 1089, 3762, 192, 454, 4306, 3639, 4474, 922, 3108, 3562, 4901, 3098, 1530, 4893, 719, 1557, 1315, 4221, 3229, 3512, 1603, 4818, 1892, 1568, 1724, 3318, 2978, 2275, 3206, 2692, 1364, 4657, 2378, 5199, 4471, 5130, 1542, 1081, 447, 4519, 14, 5143, 4783, 2976, 3715, 3863, 728, 838, 3754, 475, 1110, 1375, 1139, 2644, 3109, 197, 3759, 2241, 1702, 667, 2199, 915, 3070, 1685, 540, 3474, 3372, 4354, 1608, 5105, 2781, 1841, 3633, 1895, 2316, 3044, 3009, 2867, 3090, 2639, 4082, 2819, 4987, 3526, 4700, 3228, 1308, 976, 4039, 924, 4908, 925, 705, 3106, 0, 1390, 2204, 2676, 1778, 2983, 1662, 767, 2453, 4937, 3299, 300, 480, 4772, 2464, 2760, 5205, 3858, 759, 2436, 2776, 223, 1898, 2452, 5121, 3820, 3128, 830, 2842, 3088, 2590, 3393, 199, 2284, 3442, 4836, 1998, 4924, 2407, 2862, 4352, 4687, 1997, 2186, 4114, 3721, 4819, 362, 2814, 4345, 3449, 4935, 714, 1919, 2525, 617, 2415, 4807, 2431, 3994, 1279, 3233, 895, 902, 876, 4583, 762, 1189, 411, 632, 2561, 1230, 4855, 1104, 45, 4996, 4922, 2345, 2064, 4725, 1122, 2079, 912, 4626, 1937, 1280, 2004, 4443, 1131, 1254, 460, 1407, 3773, 4325, 1228, 5116, 2012, 1767, 4787, 4749, 3567, 4480, 4576, 4936, 365, 5063, 3768, 2775, 5087, 20, 71, 2646, 715, 3337, 4018, 3608, 3156, 523, 3481, 3756, 1733, 1273, 3750, 598, 857, 2796, 2585, 4880, 3713, 4619, 791, 4300, 2716, 4852, 828, 1871, 1579, 4756, 1865, 4420, 4769, 2848, 3347, 3364, 2581, 2084, 3129, 3099, 2268, 3217, 2274, 1346, 4720, 371, 3169, 788, 1734, 2913, 180, 918, 5194, 931, 879, 1969, 157, 3371, 272, 2389, 1795, 3683, 361, 1532, 2102, 2427, 366, 2391, 1728, 5203, 4030, 3868, 2264, 2630, 1845, 9, 3187, 1065, 1365, 4280, 130, 1700, 3686, 421, 25, 1458, 747, 4827, 4842, 5208, 2700, 3796, 2405, 4523, 5009, 1965, 1130, 2695, 3854, 2013, 2518, 2763, 960, 3121, 921, 4696, 4490, 1596, 4754, 4590, 3192, 858, 1628, 3905, 573, 4667, 2441, 645, 270, 2466, 3135, 2367, 4645, 3019, 3673, 4416, 1399, 2605, 3894, 1461, 5137, 2117, 1022, 1541, 4520, 599, 2146, 805, 5119, 3185, 5020, 751, 1436, 2226, 5152, 458, 535, 4285, 1605, 3487, 3797, 651, 1674, 3352, 2637, 4106, 1253, 5024, 713, 2894, 3739, 3751, 4472, 1353, 3577, 4424, 4180, 4814, 5211, 1934, 1746, 1570, 3712, 1417, 967, 150, 289, 1416, 1683, 4521, 4431, 385, 616, 2847, 1944, 5022, 113, 3842, 4036, 5189, 1787, 2247, 102, 3847, 1698, 3766, 4489, 1268, 3975, 1180, 690, 4339, 1233, 1479, 1576, 5165, 2293, 4484, 3270, 66, 3035, 2353, 60, 4113, 19, 3231, 2179, 1054, 2400, 4031, 1009, 1014, 3563, 4070, 2554, 1314, 4091, 2768, 3874, 3584, 278, 4710, 539, 2987, 1358, 3306, 749, 1050, 688, 5057, 3234, 3536, 1355, 2871, 1063, 1675, 971, 3833, 635, 3592, 1874, 2265, 1722, 162, 884, 357, 983, 3688, 961, 3738, 3573, 559, 3533, 2868, 1239, 2008, 3588, 2181, 2837, 4914, 2501, 3826, 1201, 3627, 627, 1057, 878, 4132, 2658, 1820, 1091, 2100, 4640, 4083, 4529, 569, 3616, 2473, 4931, 1972, 3915, 4548, 1543, 2715, 1566, 1035, 3586, 1709, 3385, 829, 2062, 2610, 698, 3267, 2906, 2774, 2399, 3170, 4790, 3151, 4050, 3383, 64, 3585, 3036, 333, 1420, 4925, 2839, 1789, 1616, 1837, 2256, 1007, 2097, 3935, 2347, 120, 4923, 2980, 794, 1077, 2471, 2918, 988, 3286, 4369, 737, 4465, 4686, 1764, 4457, 2463, 1968, 582, 3594, 1738, 3734, 4357, 1463, 4630, 5138, 2807, 1903, 3687, 4479, 1832, 4171, 4971, 4777, 753, 609, 360, 981, 4984, 4442, 4493, 3953, 1949, 1958, 4124, 1166, 3349, 4417, 2849, 5091, 1810, 2908, 1753, 396, 1097, 3618, 4854, 1770, 1620, 3787, 2502, 4531, 4080, 1942, 2465, 768, 716, 4879, 4939, 3063, 817, 3142, 1106, 4934, 3498, 3461, 4528, 1456, 2936, 1378, 2717, 4213, 2966, 3779, 2914, 4087, 4949, 5097, 2659, 2093, 1397, 5209, 2891, 1689, 1379, 1484, 3553, 2615, 1034, 4274, 861, 3726, 652, 5198, 3163, 680, 2551, 1094, 2739, 2154, 2167, 1771, 265, 3942, 5092, 382, 164, 3343, 3418, 4995, 2287, 2944, 2306, 2272, 1954, 4214, 41, 936, 1291, 2738, 3363, 1956, 2438, 644, 3499, 405, 1866, 529, 3976, 3709, 4767, 4149, 2129, 2336, 3660, 1517, 3152, 1926, 1200, 2122, 1123, 5196, 4121, 1971, 4310, 1721, 3677, 2456, 2283, 129, 2582, 425, 2386, 3477, 2996, 543, 189, 4584, 5159, 4812, 392, 3848, 4005, 1867, 3155, 4912, 696, 3668, 2053, 4712, 1046, 913, 5170, 1473, 807, 584, 911, 1661, 5016, 4360, 288, 52, 1991, 4437, 1098, 1881, 1621, 2664, 3425, 4495, 1987, 2544, 452, 242, 2670, 4697, 1703, 1755, 3728, 2601, 492, 4728, 3767, 2447, 4551, 3476, 1529, 906, 2087, 3844, 2218, 1615, 4072, 2298, 1277, 236, 1634, 1653, 2472, 1920, 1654, 3397, 2657, 2931, 5181, 4166, 3784, 2832, 987, 1489, 339, 2994, 142, 4892, 5127, 3801, 959, 1083, 3252, 3561, 1136, 1038, 3368, 3923, 4863, 732, 2642, 1109, 968, 4024, 1385, 905, 4709, 2036, 1439, 2349, 1149, 679, 3344, 146, 1249, 1896, 1578, 5073, 1843, 5069, 2724, 3900, 4618, 5072, 4512, 4224, 3406, 2137, 549, 2295, 2021], 'dvalid': [2370, 2945, 3399, 948, 2649, 4229, 4664, 4665, 4056, 5021, 2726, 1676, 1522, 4627, 3843, 3458, 1124, 4059, 3285, 1267, 4970, 3675, 2710, 1258, 4733, 1905, 1741, 316, 1977, 2276, 4021, 2571, 562, 2504, 1768, 4170, 5014, 3908, 2743, 1995, 358, 3200, 846, 2546, 2340, 4699, 2618, 4390, 3732, 4510, 3317, 3877, 4741, 2394, 2131, 2365, 3420, 2647, 1776, 4470, 3603, 3041, 3353, 4508, 5150, 2026, 2069, 2545, 5077, 890, 5051, 4276, 4800, 1400, 4347, 2888, 1556, 2943, 4947, 4938, 3340, 62, 5042, 2255, 1751, 3911, 4189, 1128, 727, 1762, 2379, 4099, 4876, 3483, 2794, 3167, 450, 4805, 1184, 1801, 3259, 2451, 5179, 2088, 5039, 2366, 4011, 533, 16, 1283, 607, 4164, 1935, 2575, 695, 84, 320, 3793, 2971, 3046, 2818, 2317, 2435, 2082, 489, 3065, 1181, 692, 220, 3947, 2771, 2348, 8, 394, 3071, 1026, 4358, 4123, 5095, 375, 2333, 3209, 4245, 496, 2731, 3548, 99, 2721, 1324, 3417, 2587, 3655, 2947, 3685, 1126, 4242, 2563, 4653, 4477, 2593, 2834, 5108, 3105, 5080, 5200, 4723, 865, 2925, 2620, 2459, 2812, 336, 1058, 975, 3731, 949, 4309, 3182, 2141, 5125, 2902, 3846, 3772, 910, 1352, 799, 561, 1382, 777, 2855, 4290, 2539, 1206, 4165, 4160, 3261, 514, 2719, 3666, 4139, 2633, 4371, 3806, 2702, 1343, 104, 439, 4506, 842, 5089, 956, 1678, 2056, 4825, 3890]}, 'Client1': {'dtrain': [4758, 2600, 4203, 3164, 2165, 5013, 4062, 4751, 2208, 433, 4766, 4389, 1737, 2948, 2051, 748, 3450, 3614, 3640, 784, 1339, 2619, 3809, 1673, 1108, 766, 4918, 534, 3288, 547, 3333, 2566, 3069, 2094, 2257, 3609, 4066, 3841, 2393, 641, 1183, 3743, 2762, 3133, 2696, 831, 2417, 4574, 1916, 1116, 672, 3431, 1697, 3208, 4774, 3173, 5033, 3052, 4607, 3729, 1582, 1023, 355, 5185, 4998, 1924, 4074, 4146, 1288, 258, 2303, 2426, 3996, 5090, 3153, 1827, 3413, 2982, 2682, 4543, 2899, 605, 1028, 3891, 4292, 1833, 134, 1980, 494, 347, 3166, 2517, 4976, 3429, 4430, 4785, 625, 4571, 763, 3470, 76, 3379, 787, 4441, 1223, 2912, 4055, 1047, 583, 3324, 3678, 2057, 5210, 2541, 1312, 4953, 1854, 4649, 1520, 2625, 774, 186, 2478, 4847, 3126, 2396, 1003, 5010, 1222, 1135, 782, 3543, 3669, 379, 4186, 3550, 59, 4808, 207, 4060, 3205, 3227, 3275, 4109, 4562, 2123, 4094, 3946, 2884, 5048, 4668, 4603, 4641, 4635, 3977, 4561, 5029, 145, 2521, 4753, 1078, 4958, 386, 4076, 4337, 1336, 1293, 3706, 387, 1962, 10, 4311, 4565, 1468, 4582, 3378, 3886, 368, 3695, 3409, 3896, 3520, 2992, 1707, 933, 3951, 35, 5139, 1506, 1786, 4234, 1248, 3748, 1247, 4235, 203, 1389, 1276, 4759, 4727, 4522, 4588, 211, 4796, 4830, 503, 2793, 1300, 5062, 4839, 3124, 4658, 1469, 4144, 1170, 739, 3280, 4724, 3537, 2343, 3003, 237, 3161, 271, 3672, 994, 4945, 3699, 2020, 263, 844, 4303, 3920, 1409, 3828, 4370, 3322, 2591, 2969, 5047, 3001, 2322, 1394, 4317, 723, 2484, 898, 1744, 22, 3825, 578, 4270, 2476, 110, 3538, 228, 2455, 274, 125, 1232, 4776, 4427, 3444, 3534, 3879, 3954, 4177, 1640, 764, 341, 2740, 1781, 2784, 947, 800, 5052, 3597, 531, 1320, 3020, 2998, 5161, 2470, 2748, 2101, 3457, 4556, 3576, 1209, 4014, 2764, 779, 4638, 4614, 2729, 248, 1360, 802, 954, 1313, 3887, 4747, 2904, 860, 3104, 4572, 770, 2728, 46, 634, 4377, 1141, 2215, 4141, 4315, 4259, 4778, 2531, 1679, 2, 4110, 3416, 4079, 2373, 991, 4801, 3332, 1036, 4629, 2188, 5011, 2536, 2713, 2178, 4486, 1838, 4447, 2164, 3077, 5153, 3583, 1939, 4257, 3936, 3551, 642, 3148, 4108, 2027, 3123, 789, 1802, 4621, 2046, 740, 4026, 1690, 3315, 1441, 2371, 3215, 3987, 3482, 1883, 3282, 4426, 606, 2143, 1580, 133, 1891, 4694, 1572, 4231, 2999, 2836, 1450, 1427, 3629, 3840, 2638, 4286, 597, 3746, 3139, 1410, 4200, 3454, 4518, 3785, 2061, 4318, 2858, 152, 4594, 2390, 677, 26, 1402, 4343, 282, 3171, 2120, 4513, 4429, 504, 2335, 806, 3689, 646, 1004, 101, 4906, 2820, 2106, 4405, 4467, 1307, 3869, 4199, 1873, 5065, 3790, 2285, 4885, 2067, 28, 510, 568, 4151, 790, 4672, 4254, 864, 221, 5148, 4196, 2411, 621, 3360, 517, 3358, 3149, 2826, 3918, 2516, 985, 1622, 1424, 3819, 2614, 2723, 1306, 121, 1524, 1684, 269, 1996, 2419, 1231, 4498, 1984, 3924, 1263, 3696, 2458, 5056, 1085, 4215, 1766, 2314, 2972, 4209, 3862, 2468, 3542, 886, 3412, 1243, 4482, 2182, 2795, 4294, 4406, 4615, 3086, 3664, 119, 1030, 147, 3225, 4169, 3250, 495, 3749, 2866, 4698, 1322, 4262, 1694, 3101, 3264, 3523, 4168, 3979, 4636, 1932, 3426, 4344, 4439, 3147, 1842, 481, 592, 3617, 1235, 848, 4067, 4848, 1567, 4821, 3223, 4597, 285, 4540, 3188, 3361, 3309, 684, 940, 1499, 2492, 2933, 2798, 2077, 3650, 1021, 2002, 1159, 1594, 443, 1425, 4223, 3717, 3736, 3631, 4951, 30, 548, 4496, 4273, 2584, 4973, 2245, 291, 1806, 3961, 2752, 3735, 3838, 978, 862, 3599, 1445, 4028, 5140, 1817, 2962, 4593, 3752, 3925, 4610, 1100, 2334, 4243, 2838, 571, 2037, 3647, 3049, 4412, 3674, 4497, 1763, 3007, 132, 1889, 2450, 4328, 1585, 4752, 2662, 2953, 4454, 80, 5129, 3989, 4237, 2889, 1807, 2151, 403, 3219, 1742, 1068, 3949, 1395, 4009, 1168, 4612, 3757, 4007, 4308, 2073, 3919, 990, 3971, 395, 686, 3571, 4866, 4983, 3042, 4069, 3307, 4435, 4155, 1590, 3501, 4804, 2995, 1593, 4853, 4536, 4617, 1348, 853, 296, 2220, 2973, 1671, 5044, 3089, 1076, 2318, 4085, 1505, 3327, 2049, 1476, 3855, 1302, 4375, 2374, 3066, 2927, 2054, 2315, 3867, 2879, 1190, 1928, 98, 2311, 2475, 3737, 2510, 139, 2192, 3102, 3218, 3913, 2269, 1012, 2608, 5076, 2930, 2090, 2613, 4, 877, 111, 3277, 177, 2500, 3056, 3720, 995, 3471, 4363, 1917, 564, 773, 1558, 5164, 2328, 4834, 2856, 1860, 487, 1226, 5202, 522, 3265, 2741, 2442, 3245, 1478, 1693, 1643, 5123, 2722, 2672, 1839, 83, 1289, 3068, 38, 2035, 1876, 54, 4277, 1216, 1199, 2382, 1311, 1648, 3875, 1533, 4249, 3475, 428, 2892, 3296, 2490, 3201, 5207, 4644, 1877, 1331, 409, 384, 2960, 3681, 350, 198, 4823, 3131, 855, 4075, 3183, 4324, 555, 1240, 3730, 3367, 2817, 4642, 5045, 4846, 202, 309, 226, 40, 3711, 2576, 3301, 4648, 1974, 473, 2372, 3697, 2924, 1948, 200, 3478, 3325, 4319, 1915, 1641, 3502, 2704, 4549, 209, 2007, 4305, 3831, 2219, 2509, 313, 314, 306, 4278, 631, 3037, 3774, 1351, 1500, 1150, 866, 3246, 2462, 1509, 2788, 1357, 3321, 1864, 2990, 4788, 3390, 2038, 804, 4682, 538, 3025, 873, 883, 233, 4101, 1550, 4129, 3391, 1999, 5015, 3623, 4864, 377, 3240, 4499, 1287, 1101, 2830, 4004], 'dvalid': [2594, 2876, 3193, 2574, 5171, 2860, 1066, 1053, 1002, 2685, 2147, 4850, 118, 318, 1516, 4564, 2660, 4860, 3370, 63, 1658, 3473, 1119, 4202, 4455, 3394, 2684, 1266, 34, 893, 3645, 217, 1503, 4287, 4960, 4040, 4989, 4504, 2085, 2489, 3278, 4154, 4134, 343, 2404, 3960, 1523, 851, 1452, 136, 4750, 1152, 4910, 3033, 5004, 159, 1574, 1719, 4316, 173, 2519, 4204, 3605, 1391, 3637, 2712, 1870, 3547, 3795, 3632, 2589, 4670, 246, 5118, 5074, 3978, 3114, 2239, 3312, 3634, 674, 2185, 2567, 2176, 4053, 4002, 2003, 4133, 3058, 3346, 1519, 4803, 639, 2932, 3491, 2434, 2683, 4634, 2661, 436, 2959, 5081, 820, 474, 3615, 3381, 2939, 4159, 3799, 3072, 5046, 4775, 1072, 3937, 116, 2651, 2430, 1899, 2828, 1440, 2339, 2556, 3210, 5053, 4647, 3313, 2679, 2678, 4757, 3593, 4033, 2737, 4828, 466, 3405, 4107, 1146, 2923, 3294, 1250, 2240, 1137, 4916, 1872, 4673, 1350, 2497, 2880, 3765, 2624, 736, 1945, 3667, 235, 4888, 245, 1434, 2553, 1342, 4331, 2911, 5012, 2362, 552, 3062, 3004, 4734, 3968, 57, 754, 426, 4461, 4197, 2727, 824, 859, 2806, 5031, 3486, 2118, 4494, 3812, 3266, 4651, 1207, 4877, 4057, 2070, 1376, 3884, 745, 4392, 1879, 4940, 1491, 1193, 4795, 429, 1292, 1537, 3693, 2958, 4707, 4043, 699, 2059, 3725, 5141, 1912]}, 'Client2': {'dtrain': [1242, 4631, 434, 1347, 1366, 1082, 1186, 4258, 4611, 457, 479, 1659, 383, 2935, 1488, 2599, 2414, 2552, 1758, 2526, 3241, 3435, 3967, 5018, 2136, 3158, 4859, 3232, 1960, 2300, 3644, 3074, 4889, 2970, 2937, 1217, 818, 4126, 4894, 4459, 1780, 3382, 3902, 2565, 188, 2033, 420, 3380, 4956, 4143, 536, 1025, 4421, 3107, 4678, 4746, 2439, 2578, 3125, 5032, 2177, 1372, 2694, 3251, 565, 5003, 2425, 1167, 4211, 2503, 917, 1711, 3428, 1730, 3763, 5212, 112, 671, 4176, 4882, 4162, 3575, 5191, 4393, 1617, 441, 4228, 244, 3804, 901, 3529, 4646, 2753, 2520, 1921, 2252, 4881, 2558, 4288, 4230, 4977, 1713, 4338, 2967, 4792, 3396, 2595, 322, 839, 590, 1765, 3866, 1298, 1160, 869, 2361, 5026, 3704, 4606, 423, 4690, 685, 1599, 3991, 2099, 4064, 262, 2707, 3145, 2031, 3718, 323, 3060, 1296, 4662, 868, 2250, 27, 1850, 2416, 919, 5195, 3545, 4898, 1587, 4341, 3165, 3941, 158, 1852, 4481, 3080, 3822, 2071, 4865, 393, 1600, 4563, 3176, 4744, 2780, 106, 75, 1828, 952, 615, 3525, 525, 3281, 3897, 225, 29, 4226, 3496, 1208, 1120, 3174, 4256, 1571, 3254, 4986, 4537, 742, 1444, 1349, 3861, 2514, 2249, 3423, 2258, 1862, 2440, 4897, 821, 4157, 610, 3939, 1011, 2116, 1430, 2403, 1299, 4843, 2580, 4217, 2851, 554, 4220, 2209, 4954, 4103, 2065, 4488, 4201, 5146, 1947, 4738, 58, 4815, 2893, 2568, 2756, 2815, 4789, 413, 5182, 998, 1731, 5054, 328, 1117, 24, 1835, 4919, 501, 153, 415, 5094, 4944, 637, 2074, 722, 4742, 3357, 4507, 3956, 1316, 390, 1869, 4156, 3207, 989, 2246, 3878, 2507, 977, 3566, 2277, 1220, 3507, 1475, 2783, 2360, 4857, 1978, 1140, 2863, 3366, 2420, 4652, 2011, 372, 4307, 4423, 1096, 835, 1849, 2133, 4965, 73, 5088, 2445, 374, 3509, 2221, 3085, 814, 1562, 2957, 254, 304, 4089, 4770, 1501, 2952, 4675, 3701, 1931, 3830, 4458, 2532, 3517, 1405, 4175, 1271, 1627, 4822, 1528, 2124, 3554, 4379, 1438, 1631, 4740, 3136, 1514, 5059, 4755, 3676, 3873, 963, 3707, 1006, 462, 4639, 2705, 2005, 2747, 2010, 422, 103, 4419, 4404, 2095, 3680, 4150, 1918, 2872, 3892, 1799, 3540, 448, 3191, 3255, 3611, 42, 3986, 4974, 1769, 957, 3791, 1227, 87, 206, 2759, 2017, 2172, 4145, 941, 560, 1840, 955, 1055, 2797, 2000, 367, 4483, 2559, 3952, 456, 1936, 2248, 1754, 3601, 5, 148, 140, 4283, 3016, 5041, 3137, 3452, 297, 327, 1147, 185, 1330, 4135, 1498, 3127, 2623, 3295, 837, 183, 2981, 2352, 558, 783, 3051, 2909, 3237, 4218, 4194, 3350, 3064, 2543, 4718, 3708, 3679, 881, 2669, 1414, 1362, 1086, 2631, 1451, 4835, 463, 1793, 3549, 4946, 2845, 4620, 1808, 3933, 1547, 717, 3459, 1756, 1234, 2602, 1333, 5134, 165, 4051, 3539, 2018, 414, 792, 3480, 5107, 3531, 187, 1665, 4693, 3437, 1706, 431, 2640, 2212, 1857, 238, 648, 2941, 813, 2150, 4296, 593, 2675, 2312, 815, 1714, 1632, 5093, 1910, 2667, 1103, 3511, 127, 1604, 3084, 1525, 4674, 3932, 1851, 3341, 796, 1538, 1637, 3197, 5113, 4449, 4451, 1017, 1606, 2803, 3002, 1341, 1043, 604, 2698, 4874, 2800, 765, 2377, 3596, 3771, 4586, 587, 2113, 2733, 351, 3794, 114, 2895, 2217, 1325, 1526, 2288, 3093, 3095, 2488, 5007, 781, 5172, 1428, 3938, 135, 579, 3527, 1897, 4806, 2542, 4688, 1663, 2409, 239, 5162, 3646, 4837, 61, 5023, 4798, 2961, 2291, 3045, 4373, 4063, 3535, 232, 1027, 603, 4932, 2841, 5070, 280, 4955, 1715, 2720, 3630, 1794, 4452, 3803, 3625, 2907, 293, 3692, 521, 2597, 69, 2356, 4721, 4178, 3600, 3714, 493, 5128, 2448, 3244, 2331, 1497, 3641, 4260, 3199, 4364, 1156, 2461, 417, 1511, 856, 4182, 1743, 4246, 2047, 4195, 1371, 4172, 397, 2915, 2281, 4509, 3443, 2161, 3560, 601, 2874, 3997, 3661, 5156, 4222, 1691, 241, 1660, 65, 4372, 636, 4867, 3154, 2919, 2449, 1295, 3857, 2583, 3132, 3959, 2040, 4247, 195, 2187, 1798, 1392, 4659, 4284, 750, 3258, 181, 3988, 875, 319, 1504, 2665, 3146, 2016, 4380, 2612, 205, 2495, 2153, 3057, 2787, 5111, 1635, 1129, 4244, 4568, 4655, 1642, 5100, 3398, 1788, 687, 2171, 4656, 445, 3179, 442, 2529, 3211, 4198, 1245, 942, 194, 4184, 275, 2654, 3073, 825, 809, 734, 4313, 3462, 4896, 4326, 3636, 4714, 4463, 5115, 4871, 2487, 4188, 1651, 4501, 3489, 4111, 3808, 1396, 2127, 4502, 2916, 4567, 2125, 3415, 1188, 2329, 4570, 3239, 2048, 4824, 5186, 1229, 4403, 575, 744, 1111, 2491, 2709, 2045, 1612, 3500, 1257, 1791, 2200, 1772, 4029, 746, 1502, 5183, 1133, 1486, 656, 3775, 1584, 3010, 3786, 4533, 1950, 3883, 2688, 3612, 5215, 553, 891, 4052, 2358, 1171, 218, 340, 2479, 2955, 2309, 4719, 78, 1483, 3929, 1114, 1462, 1112, 1272, 619, 958, 3899, 3419, 4526, 2260, 3654, 3719, 3782, 1455, 2304, 3916, 4554, 2229, 215, 3572, 3186, 2732, 1667, 1037, 4118, 4006, 4299, 950, 2196, 376, 1487, 4349, 3671, 4293, 264, 2934, 3013, 2313, 2674, 2940, 5187, 2827, 1260, 3190, 4826, 1310, 1712, 4492, 37, 4539, 570, 1019, 1060, 871, 2865, 3926, 2641, 3048, 4538, 4598, 2469, 4253, 623, 4208, 1492, 4158, 1575, 3014, 334, 1773], 'dvalid': [2395, 1933, 2910, 2744, 1792, 4856, 867, 1858, 4025, 4927, 1384, 4799, 760, 622, 5168, 3320, 3022, 786, 3043, 168, 401, 2677, 4127, 4239, 1626, 438, 2949, 408, 3764, 880, 5192, 1645, 4012, 3243, 4440, 3026, 2368, 4187, 3392, 3912, 4084, 3602, 4831, 3889, 4374, 2920, 1155, 2481, 2228, 2846, 2622, 3196, 4207, 1581, 908, 2779, 4236, 1040, 1102, 1165, 2611, 5154, 4726, 476, 793, 3590, 1644, 2690, 4793, 2596, 4780, 5001, 4930, 3852, 4552, 3351, 5082, 2785, 551, 1989, 2645, 1194, 701, 1087, 2437, 1884, 1809, 3504, 515, 1107, 1800, 1177, 3663, 1270, 1127, 2130, 4073, 3110, 3030, 3076, 499, 400, 2083, 1198, 546, 4532, 484, 219, 1118, 290, 5131, 3100, 4266, 4545, 3909, 4650, 4061, 4032, 3515, 4174, 4453, 979, 1975, 398, 1821, 2387, 5151, 520, 1539, 1761, 166, 2323, 4975, 3598, 4683, 4560, 4553, 1718, 3834, 2627, 1493, 620, 4485, 1834, 4444, 3740, 4411, 2666, 1426, 5180, 1148, 301, 295, 585, 731, 369, 2607, 2634, 3702, 1125, 1256, 2758, 1269, 1237, 2041, 4264, 2751, 3963, 2242, 3622, 1327, 505, 3116, 4717, 647, 4008, 1429, 4868, 969, 3656, 2482, 5034, 4838, 1255, 424, 1701, 4382, 4810, 2412, 4928, 4861, 1609, 3651, 3434, 122, 4684, 2327, 2155, 4487, 3339, 1485, 3760, 557, 2745]}, 'Client3': {'dtrain': [4096, 4577, 769, 1797, 4329, 1205, 1861, 2231, 4219, 1885, 3005, 3810, 79, 149, 2410, 4669, 3742, 1264, 785, 4022, 4691, 5101, 1624, 2030, 1403, 266, 4034, 4414, 1178, 1961, 3230, 4391, 3248, 485, 581, 3503, 5078, 2310, 2917, 356, 2126, 939, 1979, 4832, 2299, 2835, 2032, 2711, 67, 516, 4550, 21, 2223, 4969, 1732, 2135, 951, 3118, 55, 1619, 1666, 3662, 2043, 108, 4137, 541, 2528, 3985, 2985, 3983, 1670, 2354, 4054, 3053, 1013, 5103, 2174, 2735, 3657, 1512, 268, 2351, 2734, 526, 3931, 1573, 4516, 1677, 305, 3178, 532, 2701, 4613, 1419, 4167, 3798, 4589, 1196, 3703, 247, 1540, 3097, 3488, 1824, 2280, 3745, 1655, 4542, 3204, 693, 5126, 712, 4227, 5106, 1717, 4625, 4844, 3705, 1727, 3495, 1359, 4820, 2616, 1811, 2746, 4001, 4579, 4097, 4327, 1446, 3403, 4905, 2761, 854, 143, 3589, 3816, 5068, 4909, 1900, 1822, 261, 2166, 2110, 4090, 3029, 1281, 4179, 3532, 3464, 1421, 4428, 1784, 3236, 6, 3792, 1275, 3257, 2900, 2938, 4786, 661, 720, 1470, 1686, 2198, 3578, 1909, 3621, 1952, 1695, 3323, 5075, 1774, 1224, 2092, 329, 563, 797, 5102, 1583, 3839, 659, 2550, 1176, 2809, 2152, 3293, 3513, 761, 1959, 4849, 2170, 1164, 1153, 3284, 427, 1847, 4402, 2693, 4295, 2573, 1453, 1914, 904, 1664, 2142, 882, 4399, 2392, 174, 3079, 2290, 4514, 252, 914, 4654, 1760, 1412, 5036, 2977, 2009, 945, 3910, 2579, 1629, 2075, 3034, 506, 1823, 3505, 608, 4869, 348, 4575, 2951, 2107, 1174, 1032, 1775, 5190, 1710, 446, 2882, 1554, 4468, 1647, 4555, 435, 1361, 1175, 1048, 2572, 2148, 1067, 1297, 611, 4045, 4895, 3871, 2708, 1633, 3342, 3958, 48, 3727, 2332, 2890, 4623, 530, 4116, 1477, 4122, 4330, 1515, 2034, 4689, 1321, 213, 2344, 4193, 5058, 3189, 3202, 1092, 618, 5149, 4985, 2384, 100, 461, 2485, 822, 843, 3465, 2673, 4436, 2954, 3050, 4016, 743, 4252, 2460, 2643, 3177, 1636, 613, 1610, 577, 128, 3582, 3094, 1729, 4816, 4524, 4902, 624, 1303, 633, 2557, 3999, 4185, 542, 3263, 1739, 1383, 1563, 2901, 4708, 1480, 3316, 1367, 2207, 2114, 3283, 3256, 4216, 4314, 1323, 88, 2369, 1657, 2210, 2015, 449, 1785, 4731, 3649, 230, 4321, 932, 3777, 1210, 2224, 1073, 2515, 4410, 4771, 287, 3083, 3569, 2843, 1951, 4049, 3895, 4891, 2844, 2401, 4764, 4573, 5086, 1284, 4433, 3821, 4048, 4425, 3716, 1454, 3469, 2617, 4990, 1986, 3579, 1158, 3103, 4462, 51, 1894, 331, 2320, 1008, 1591, 2792, 1418, 2159, 3384, 1029, 2140, 2656, 469, 2158, 3445, 5006, 2253, 1442, 3970, 4183, 2359, 298, 5061, 2381, 4715, 3973, 3658, 1344, 2754, 3269, 1079, 4730, 3805, 1211, 4255, 4982, 3723, 2765, 3568, 2216, 4251, 4794, 1318, 2718, 4604, 5132, 1887, 2251, 1555, 2850, 3955, 3524, 4503, 2350, 4336, 1024, 1061, 5157, 1449, 2109, 528, 5136, 629, 580, 772, 2592, 4044, 326, 953, 3448, 1552, 2655, 509, 1151, 1818, 2066, 1882, 3556, 1831, 2486, 1304, 1836, 738, 3555, 4233, 1716, 4120, 4291, 3642, 389, 4929, 1531, 267, 1334, 2096, 294, 2881, 4903, 212, 3966, 2346, 2294, 1380, 703, 3302, 137, 2513, 702, 1415, 4281, 1154, 1750, 3948, 1853, 3078, 4605, 663, 399, 4872, 5214, 2189, 94, 1282, 404, 3157, 1329, 4323, 3722, 4633, 3741, 4010, 4035, 3297, 5163, 1191, 3369, 3832, 512, 4238, 3220, 3021, 1829, 655, 3144, 3012, 2805, 56, 1051, 3017, 4546, 2044, 281, 184, 997, 3510, 3800, 1374, 4920, 894, 5145, 3783, 3557, 1093, 2956, 2767, 3268, 3893, 2342, 330, 1911, 572, 4397, 2859, 2816, 1507, 4685, 1736, 4500, 5193, 3544, 4267, 4476, 4312, 4361, 1816, 324, 4346, 2262, 1368, 3087, 930, 4381, 1326, 836, 4535, 2301, 4322, 3031, 3195, 1982, 1913, 3850, 2134, 2042, 2193, 2499, 370, 3287, 3221, 3508, 2905, 5027, 4525, 666, 1386, 4845, 4735, 497, 4870, 4398, 279, 2302, 4761, 4131, 2168, 1262, 4181, 2183, 2974, 3945, 4140, 1431, 3516, 1495, 3175, 4351, 2173, 1846, 2530, 4884, 1748, 36, 1338, 3998, 216, 1782, 3964, 507, 3780, 5083, 308, 2782, 1443, 3373, 4088, 1534, 706, 4415, 4580, 3242, 2058, 3334, 171, 2454, 1172, 1138, 1182, 1650, 2522, 2050, 4762, 5197, 483, 3365, 4142, 3047, 1752, 816, 3907, 3901, 5000, 2829, 3331, 4212, 1099, 3753, 4334, 1705, 586, 4679, 4261, 1546, 3865, 2325, 4962, 2786, 2853, 163, 2598, 1252, 2108, 1611, 1639, 1687, 2278, 2429, 700, 191, 4263, 4643, 801, 33, 311, 2202, 2736, 1218, 2946, 1561, 649, 2149, 4628, 3276, 3000, 3387, 3769, 4408, 2321, 444, 131, 437, 986, 2750, 3564, 3604, 3811, 3400, 2778, 5184, 18, 2098, 3876, 3162, 928, 2725, 2319, 1708, 1976, 4967, 993, 2804, 345, 3112, 1212, 5035, 832, 2831, 735, 2380, 196, 1941, 3303, 1646, 4585, 1696, 5158, 1549, 1134, 1812, 612, 3606, 4862, 2540, 3438, 2822, 3451, 4161, 2864, 3628, 2548, 4376, 1197, 676, 418, 2297, 4301, 3690, 5085, 3453, 3441, 2852, 3038, 3456, 1607, 4745, 3096, 2689, 2878, 3290, 2194, 3818, 3355, 2138, 1680, 3113, 3150, 4840, 349, 1929, 210, 4779, 2086, 1121, 17, 3691, 3965, 1925, 4900, 2483, 2080, 524, 4152, 870, 1041, 665, 2024, 4302, 4988, 1922, 1559, 589, 1031, 897, 1964, 3395, 4883, 711, 3653, 1259, 2777, 2512, 2433, 1203, 3921, 50, 1535, 3310, 544, 3092, 3194, 353, 1813, 240, 3558, 4297, 4102, 4407, 614, 3414, 500, 4100, 4517, 124, 4609, 1144, 2757, 4173, 2562, 407, 3522, 4624, 771, 1464, 4736, 1569, 4695, 3006, 93, 556, 5206, 1294, 1745, 907, 3620, 4434, 3761], 'dvalid': [2254, 1393, 3460, 3433, 664, 3289, 410, 3928, 2650, 4851, 344, 4791, 2014, 2861, 77, 5124, 156, 4743, 527, 95, 4282, 2928, 3067, 2267, 3235, 11, 3212, 3514, 1010, 12, 1398, 2505, 3134, 4466, 900, 810, 2244, 4058, 5114, 303, 638, 2921, 1069, 321, 757, 909, 3389, 4797, 1406, 373, 4491, 3570, 91, 1601, 4622, 4527, 4148, 315, 1844, 4071, 2898, 2091, 49, 1923, 2534, 518, 1577, 3541, 847, 3778, 973, 5066, 2428, 167, 1669, 1545, 208, 4475, 2029, 4773, 1692, 81, 1363, 1638, 798, 3216, 4961, 4460, 4913, 5104, 2421, 4660, 3694, 224, 4092, 718, 4250, 2156, 2790, 2307, 4541, 459, 3059, 1790, 2636, 4192, 3922, 3888, 193, 4232, 4086, 3111, 4362, 4136, 2922, 1319, 600, 259, 2162, 2537, 97, 1042, 2296, 2169, 468, 2139, 4013, 4994, 2474, 1044, 1940, 2337, 1779, 1618, 2408, 5096, 1668, 3591, 654, 3652, 3813, 2398, 2801, 154, 4119, 4385, 5064, 3388, 1560, 2282, 1985, 4544, 4095, 3407, 3222, 5169, 721, 3613, 2877, 1981, 502, 5117, 2603, 1723, 670, 567, 2686, 4000, 123, 416, 1161, 1814, 89, 756, 234, 1411, 927, 683, 4105, 972, 1084, 1261, 1381, 4138, 1246, 826, 276, 1826, 4547, 4632, 3308, 5173, 5040, 3506, 823, 4130, 2730, 874, 1805, 3, 3635, 3377, 5204, 934, 4829, 3747, 3172, 974, 2423, 2072, 4915, 662, 4566, 160, 1459, 2560, 4530, 2273, 2180]}, 'Client4': {'dtrain': [3181, 5084, 2144, 1955, 3849, 4887, 1749, 5109, 4041, 3054, 117, 4335, 3075, 5201, 2385, 3082, 1354, 292, 4875, 2076, 151, 3856, 5147, 1510, 1625, 3698, 299, 3974, 4003, 1074, 1195, 4601, 3424, 4763, 4933, 4268, 819, 2413, 1783, 3559, 2261, 5049, 2965, 251, 2926, 3213, 2444, 1301, 2119, 412, 3226, 2211, 222, 1551, 2105, 2388, 3493, 2355, 3860, 1460, 4964, 1340, 3494, 250, 1185, 5144, 3864, 1039, 201, 4359, 741, 256, 1859, 4886, 107, 1943, 3815, 1681, 3479, 337, 4921, 338, 3638, 182, 4413, 1970, 4841, 4017, 3682, 4448, 3300, 944, 4732, 1990, 2081, 5071, 260, 5037, 1777, 2019, 3463, 640, 3917, 161, 3940, 3930, 4671, 2259, 5160, 3880, 44, 430, 1521, 4784, 2527, 1482, 5213, 2397, 3015, 3957, 2432, 1957, 3587, 776, 1448, 1, 3091, 3744, 4279, 673, 1370, 3853, 1757, 1005, 1088, 730, 3824, 2375, 3881, 464, 984, 2821, 4104, 992, 3138, 3159, 1815, 2770, 3906, 2668, 478, 4587, 537, 4968, 1536, 477, 4802, 1435, 691, 4760, 2621, 2648, 3898, 3271, 4943, 4093, 4396, 3436, 277, 1725, 2883, 1001, 1472, 381, 4959, 2989, 4680, 4890, 576, 363, 708, 4450, 3827, 2813, 4600, 5133, 2524, 302, 657, 2833, 1018, 653, 3404, 2799, 935, 1241, 1548, 4387, 675, 508, 406, 3851, 4739, 1236, 4981, 1855, 3440, 4386, 1759, 4456, 1404, 4768, 2467, 170, 3345, 980, 2364, 1465, 3081, 3595, 1735, 550, 1238, 455, 3304, 2480, 451, 3446, 4681, 2063, 3018, 105, 2357, 3198, 2873, 4128, 4378, 4557, 4941, 1113, 2555, 3521, 4705, 1508, 3643, 2175, 3914, 850, 3552, 2997, 2714, 780, 467, 1527, 1589, 827, 3359, 1219, 1387, 2052, 144, 3724, 2769, 3984, 3455, 4722, 1105, 402, 432, 4907, 4019, 3430, 2652, 755, 2811, 1015, 694, 2195, 2493, 4240, 658, 519, 4342, 1059, 1906, 1169, 3356, 946, 2950, 1553, 4210, 4711, 5008, 2305, 2338, 1595, 3024, 4997, 1215, 3401, 4065, 1471, 4926, 1373, 354, 2979, 1904, 3274, 4269, 889, 229, 1244, 1422, 2569, 2060, 4289, 3972, 4464, 3115, 2235, 2121, 888, 342, 4271, 630, 602, 2341, 1221, 470, 852, 1143, 3362, 3934, 3354, 3039, 3624, 3224, 2163, 1115, 1225, 3807, 138, 3432, 2363, 2897, 3291, 32, 849, 2681, 3903, 3329, 1309, 3140, 903, 812, 2197, 3659, 916, 4366, 4811, 3375, 697, 3581, 5142, 1496, 2498, 595, 752, 1413, 1630, 4676, 257, 4265, 1467, 2243, 1890, 1145, 938, 5110, 335, 3943, 4809, 1433, 2266, 2964, 2279, 962, 3467, 4333, 2547, 4388, 1447, 1056, 2538, 2477, 3870, 1090, 2326, 1597, 5055, 1688, 179, 2896, 2271, 3770, 1880, 4904, 3203, 453, 126, 249, 778, 4957, 4917, 419, 588, 3969, 3776, 2870, 2869, 725, 85, 3530, 4595, 3982, 704, 2213, 1033, 352, 4677, 3665, 3995, 1908, 4046, 3427, 2697, 3411, 4348, 2025, 4023, 4125, 4663, 4511, 4592, 488, 3376, 3472, 920, 834, 926, 3262, 2823, 96, 1049, 1045, 1214, 4368, 2840, 4409, 4147, 1830, 3249, 2494, 2286, 53, 3992, 3119, 169, 2699, 346, 4765, 1726, 965, 1290, 1938, 204, 833, 5038, 1740, 5177, 3981, 4581, 3950, 2975, 4704, 2632, 808, 3143, 5060, 1064, 1875, 4027, 1804, 2496, 3055, 1095, 1265, 2857, 1656, 2577, 660, 845, 2206, 1163, 3184, 2201, 511, 5099, 3027, 4950, 1466, 190, 4878, 1179, 1930, 574, 5112, 3610, 1993, 1886, 4706, 2289, 3904, 3180, 996, 966, 31, 378, 2184, 1016, 3120, 3466, 758, 982, 3314, 1202, 2789, 1423, 4737, 1204, 5079, 1888, 513, 491, 325, 4205, 486, 214, 896, 1518, 775, 74, 1437, 1747, 2225, 1699, 2993, 1613, 3485, 4042, 2680, 4666, 178, 1052, 1878, 13, 3684, 2330, 1251, 3122, 310, 2963, 681, 2588, 2886, 4332, 5002, 943, 1356, 1020, 923, 4979, 15, 2424, 626, 2508, 2742, 4400, 307, 4320, 1187, 3168, 4117, 92, 2671, 2270, 3130, 545, 1332, 2635, 3386, 1602, 970, 4401, 1704, 3061, 2773, 4078, 1494, 2068, 47, 2802, 1062, 3519, 4713, 1285, 4367, 3328, 255, 4015, 4980, 3305, 5028, 3845, 840, 4340, 4813, 3028, 4081, 2237, 4596, 2055, 1286, 3447, 4781, 1080, 3528, 2511, 4558, 4163, 1966, 3823, 3141, 2191, 4608, 253, 1720, 2854, 1623, 2533, 803, 2443, 4248, 4478, 4206, 1893, 724, 2023, 4602, 2825, 841, 1274, 3980, 5122, 1070, 1988, 1856, 3700, 141, 1598, 2885, 892, 4115, 3422, 440, 482, 1457, 3484, 668, 1901, 2887, 929, 4515, 176, 628, 2406, 359, 729, 710, 490, 1902, 3330, 1337, 3993, 5030, 2506, 2160, 2691, 2112, 68, 1803, 2028, 1863, 4350, 4637, 1317, 2128, 4782, 284, 1305, 1907, 5017, 2929, 4469, 4037, 3758, 1335, 1819, 4858, 3040, 4942, 2808, 2078, 3755, 4298, 5178, 2214, 4445, 4616, 885, 3311, 4225, 155, 1994, 2190, 1513, 863, 4716, 3814, 3008, 1825, 4591, 312, 391, 1973, 3032, 4833, 5025, 1490, 7, 82, 3468, 887, 3326, 4365, 689, 332, 2039, 4999, 4578, 1652, 4422, 3292, 465, 1672, 2324, 3733, 2984, 2308, 3829, 1967, 594, 2111, 3990, 2535, 1592, 5067, 231, 380, 4077, 4356, 3546, 5174, 3402, 1173, 3619, 4112, 2157, 3260, 2523, 2875, 273], 'dvalid': [2703, 4952, 1388, 3374, 3238, 1953, 5120, 2402, 795, 2222, 2115, 4418, 3648, 2236, 1071, 498, 1157, 643, 86, 1565, 4191, 2292, 1868, 596, 4038, 1564, 3348, 669, 4703, 1474, 3490, 1213, 283, 1983, 3214, 4963, 4395, 2233, 3802, 3421, 1649, 1401, 1682, 3837, 3710, 1432, 286, 3944, 115, 4190, 70, 3279, 733, 1278, 1946, 3859, 2232, 3565, 2824, 2629, 2749, 2586, 4384, 4692, 3497, 4047, 3580, 1377, 4599, 5098, 5176, 872, 4020, 364, 109, 2791, 3882, 3319, 2988, 3872, 3789, 2104, 5005, 2238, 2706, 1142, 4873, 3335, 811, 4473, 4729, 4383, 3788, 2626, 4534, 2810, 43, 4992, 4438, 4748, 3117, 2903, 4702, 2457, 3408, 1408, 4353, 472, 1614, 2653, 5155, 3272, 1963, 243, 4559, 1588, 2383, 5166, 4068, 4505, 3574, 1192, 3962, 591, 2103, 4972, 2942, 227, 1481, 4978, 2446, 2203, 1544, 3023, 5175, 899, 2766, 2968, 4446, 2564, 3607, 4569, 2609, 1927, 3885, 4275, 3781, 3670, 2991, 3011, 3626, 4993, 23, 3836, 3160, 2418, 4304, 2986, 2234, 1075, 650, 4394, 678, 3253, 3817, 3492, 72, 5043, 2422, 1328, 2263, 566, 3410, 726, 3439, 172, 2022, 2772, 5167, 4948, 2132, 3336, 4153, 2145, 3338, 937, 2230, 4272, 39, 2606, 2376, 3927, 2001, 1345, 2205, 90, 2227, 4911]}}
            ujson.dump(feddata, outf)
            #ujson.dump(vvv, outf)
        return

    def visualize_by_class(self, train_cidxs):
        import collections
        import matplotlib.pyplot as plt
        import matplotlib.colors
        import random
        ax = plt.subplots()
        colors = [key for key in matplotlib.colors.CSS4_COLORS.keys()]
        random.shuffle(colors)
        client_height = 1
        if hasattr(self, 'dirichlet_dist'):
            client_dist = self.dirichlet_dist.tolist()
            data_columns = [sum(cprop) for cprop in client_dist]
            for cid, cprop in enumerate(client_dist):
                offset = 0
                y_bottom = cid - client_height/2.0
                y_top = cid + client_height/2.0
                for lbi in range(len(cprop)):
                    plt.fill_between([offset,offset+cprop[lbi]], y_bottom, y_top, facecolor = colors[lbi])
                    # plt.barh(cid, cprop[lbi], client_height, left=offset, color=)
                    offset += cprop[lbi]
        else:
            data_columns = [len(cidx) for cidx in train_cidxs]
            for cid, cidxs in enumerate(train_cidxs):
                labels = [int(self.train_data[did][-1]) for did in cidxs]
                lb_counter = collections.Counter(labels)
                offset = 0
                y_bottom = cid - client_height/2.0
                y_top = cid + client_height/2.0
                for lbi in range(self.num_classes):
                    plt.fill_between([offset,offset+lb_counter[lbi]], y_bottom, y_top, facecolor = colors[lbi])
                    offset += lb_counter[lbi]
        plt.xlim(0,max(data_columns))
        plt.ylim(-0.5,len(train_cidxs)-0.5)
        plt.ylabel('Client ID')
        plt.xlabel('Number of Samples')
        plt.title(self.get_taskname())
        plt.savefig(os.path.join(self.taskpath, self.get_taskname()+'.jpg'))
        plt.show()


# =======================================Task Calculator===============================================
# This module is to seperate the task-specific calculating part from the federated algorithms, since the
# way of calculation (e.g. loss, evaluating metrics, optimizer) and the format of data (e.g. image, text)
# can vary in different dataset. Therefore, this module should provide a standard interface for the federated
# algorithms. To achieve this, we list the necessary interfaces as follows:
#   1) data_to_device: put the data into cuda device, since different data may differ in size or shape.
#   2) get_data_loader: get the data loader which is enumerable and returns a batch of data
#   3) get_optimizer: get the optimizer for optimizing the model parameters, which can also vary among different datasets
#   4) get_loss: the basic loss calculating procedure for the dataset, and returns loss as the final point of the computing graph
#   5) get_evaluation: evaluating the model on the dataset
# The same as TaskGenerator, we provide a default task calculator ClassifyCalculator that is suitable for datasets
# like MNIST, CIFAR100.
class BasicTaskCalculator:

    _OPTIM = None

    def __init__(self, device):
        self.device = device
        self.lossfunc = None
        self.DataLoader = None

    def data_to_device(self, data):
        raise NotImplementedError

    def train(self):
        raise NotImplementedError

    def get_evaluation(self):
        raise NotImplementedError

    def get_data_loader(self, data, batch_size=64, shuffle=True):
        return NotImplementedError

    def test(self):
        raise NotImplementedError

    def get_optimizer(self, name="sgd", model=None, lr=0.1, weight_decay=0, momentum=0):
        if self._OPTIM == None:
            raise RuntimeError("TaskCalculator._OPTIM Not Initialized.")
        if name.lower() == 'sgd':
            return self._OPTIM(model.parameters(), lr=lr, momentum=momentum, weight_decay=weight_decay)
        elif name.lower() == 'adam':
            return self._OPTIM(filter(lambda p: p.requires_grad, model.parameters()), lr=lr, weight_decay=weight_decay, amsgrad=True)
        else:
            raise RuntimeError("Invalid Optimizer.")

    @classmethod
    def setOP(cls, OP):
        cls._OPTIM = OP

class ClassificationCalculator(BasicTaskCalculator):
    def __init__(self, device):
        super(ClassificationCalculator, self).__init__(device)
        self.lossfunc = torch.nn.CrossEntropyLoss()
        self.DataLoader = DataLoader

    def train(self, model, data):
        """
        :param model: the model to train
        :param data: the training dataset
        :return: loss of the computing graph created by torch
        """
        tdata = self.data_to_device(data)
        outputs = model(tdata[0])
        loss = self.lossfunc(outputs, tdata[-1])
        return loss

    @torch.no_grad()
    def test(self, model, dataset, batch_size=64):
        """
        Metric = [mean_accuracy, mean_loss]
        :param model:
        :param dataset:
        :param batch_size:
        :return: [mean_accuracy, mean_loss]
        """
        model.eval()
        data_loader = self.get_data_loader(dataset, batch_size=64)
        total_loss = 0.0
        num_correct = 0
        for batch_id, batch_data in enumerate(data_loader):
            batch_data = self.data_to_device(batch_data)
            outputs = model(batch_data[0])
            batch_mean_loss = self.lossfunc(outputs, batch_data[-1]).item()
            y_pred = outputs.data.max(1, keepdim=True)[1]
            correct = y_pred.eq(batch_data[-1].data.view_as(y_pred)).long().cpu().sum()
            num_correct += correct.item()
            total_loss += batch_mean_loss * len(batch_data[-1])
        return {'accuracy': 1.0*num_correct/len(dataset), 'loss':total_loss/len(dataset)}

    def data_to_device(self, data):
        return data[0].to(self.device), data[1].to(self.device)

    def get_data_loader(self, dataset, batch_size=64, shuffle=True):
        if self.DataLoader == None:
            raise NotImplementedError("DataLoader Not Found.")
        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

# =====================================Task Reader\xxDataset======================================================
# This module is to read the fedtask that is generated by Generator. The target is to load the fedtask into a
# dataset inheriting from torch.utils.data.Dataset. Thus the only method read_data() should be rewriten to be suitable
# for the corresponding generating manner. With the consideration of various shapes of data, we provide mainly two ways
# for saving data and reading data:
#   1) Save the partitioned indices of items in the original dataset (e.g. torch.torchvision.*) and the path of
#      the original dataset into .json file. Then dynamically importing the original dataset when running federated training procedure,
#      and specifying each local dataset by the local indices. This function is implemented by IDXDataset and IDXTaskReader.
#      The advantages of this way include saving storing memory, high efficiency and the full usage of the torch implemention of
#      datasets in torchvision and torchspeech. Examples can be found in mnist_classification\core.py, cifar\core.py.
#
#   2) Save the partitioned data itself into .json file. Then read the data. The advantage of this way is the flexibility.
#      Examples can be found in emnist_classification\core.py, synthetic_classification\core.py, distributed_quadratic_programming\core.py.

class BasicTaskReader:
    def __init__(self, taskpath=''):
        self.taskpath = taskpath

    def read_data(self):
        """
            Reading the spilted dataset from disk files and loading data into the class 'LocalDataset'.
            This algorithm should read three types of data from the processed task:
                train_sets = [client1_train_data, ...] where each item is an instance of 'LocalDataset'
                valid_sets = [client1_valid_data, ...] where each item is an instance of 'LocalDataset'
                test_set = test_dataset
            Return train_sets, valid_sets, test_set, client_names
        """
        pass

class XYTaskReader(BasicTaskReader):
    def read_data(self):
        with open(os.path.join(self.taskpath, 'data.json'), 'r') as inf:
            feddata = ujson.load(inf)
        test_data = XYDataset(feddata['dtest']['x'], feddata['dtest']['y'])
        train_datas = [XYDataset(feddata[name]['dtrain']['x'], feddata[name]['dtrain']['y']) for name in feddata['client_names']]
        valid_datas = [XYDataset(feddata[name]['dvalid']['x'], feddata[name]['dvalid']['y']) for name in feddata['client_names']]
        return train_datas, valid_datas, test_data, feddata['client_names']

class IDXTaskReader(BasicTaskReader):
    def read_data(self):
        with open(os.path.join(self.taskpath, 'data.json'), 'r') as inf:
            feddata = ujson.load(inf)
        class_path = feddata['datasrc']['class_path']
        class_name = feddata['datasrc']['class_name']
        origin_class = getattr(importlib.import_module(class_path), class_name)
        IDXDataset.SET_ORIGIN_CLASS(origin_class)
        origin_train_data = self.args_to_dataset(feddata['datasrc']['train_args'])
        origin_test_data = self.args_to_dataset(feddata['datasrc']['test_args'])
        IDXDataset.SET_ORIGIN_DATA(train_data=origin_train_data, test_data=origin_test_data)

        test_data = IDXDataset(feddata['dtest'], key='TEST')
        train_datas = [IDXDataset(feddata[name]['dtrain']) for name in feddata['client_names']]
        valid_datas = [IDXDataset(feddata[name]['dvalid']) for name in feddata['client_names']]
        return train_datas, valid_datas, test_data, feddata['client_names']

    def args_to_dataset(self, args):
        if not isinstance(args, dict):
            raise TypeError
        args_str = '(' +  ','.join([key+'='+value for key,value in args.items()]) + ')'
        return eval("IDXDataset._ORIGIN_DATA['CLASS']"+args_str)

class XTaskReader(BasicTaskReader):
    def read_data(self):
        with open(os.path.join(self.taskpath, 'data.json'), 'r') as inf:
            feddata = ujson.load(inf)
        test_data = XDataset(feddata['dtest']['x'])
        train_datas = [XDataset(feddata[name]['dtrain']['x']) for name in feddata['client_names']]
        valid_datas = [XDataset(feddata[name]['dvalid']['x']) for name in feddata['client_names']]
        return train_datas, valid_datas, test_data, feddata['client_names']

class XYDataset(Dataset):
    def __init__(self, X=[], Y=[], totensor = True):
        """ Init Dataset with pairs of features and labels/annotations.
        XYDataset transforms data that is list\array into tensor.
        The data is already loaded into memory before passing into XYDataset.__init__()
        and thus is only suitable for benchmarks with small size (e.g. CIFAR10, MNIST)
        Args:
            X: a list of features
            Y: a list of labels with the same length of X
        """
        if not self._check_equal_length(X, Y):
            raise RuntimeError("Different length of Y with X.")
        if totensor:
            try:
                self.X = torch.tensor(X)
                self.Y = torch.tensor(Y)
            except:
                raise RuntimeError("Failed to convert input into torch.Tensor.")
        else:
            self.X = X
            self.Y = Y
        self.all_labels = list(set(self.tolist()[1]))

    def __len__(self):
        return len(self.Y)

    def __getitem__(self, item):
        return self.X[item], self.Y[item]

    def tolist(self):
        if not isinstance(self.X, torch.Tensor):
            return self.X, self.Y
        return self.X.tolist(), self.Y.tolist()

    def _check_equal_length(self, X, Y):
        return len(X)==len(Y)

    def get_all_labels(self):
        return self.all_labels

class IDXDataset(Dataset):
    # The source dataset that can be indexed by IDXDataset
    _ORIGIN_DATA = {'TRAIN': None, 'TEST': None, 'CLASS':None}

    def __init__(self, idxs, key='TRAIN'):
        """Init dataset with 'src_data' and a list of indexes that are used to position data in 'src_data'"""
        if not isinstance(idxs, list):
            raise RuntimeError("Invalid Indexes")
        self.idxs = idxs
        self.key = key

    @classmethod
    def SET_ORIGIN_DATA(cls, train_data=None, test_data=None):
        cls._ORIGIN_DATA['TRAIN'] = train_data
        cls._ORIGIN_DATA['TEST'] = test_data

    @classmethod
    def SET_ORIGIN_CLASS(cls, DataClass = None):
        cls._ORIGIN_DATA['CLASS'] = DataClass

    @classmethod
    def ADD_KEY_TO_DATA(cls, key, value = None):
        if key==None:
            raise RuntimeError("Empty key when calling class algorithm IDXData.ADD_KEY_TO_DATA")
        cls._ORIGIN_DATA[key]=value

    def __getitem__(self, item):
        idx = self.idxs[item]
        return self._ORIGIN_DATA[self.key][idx]

    def __len__(self):
        return len(self.idxs)

class TupleDataset(Dataset):
    def __init__(self, X1=[], X2=[], Y=[], totensor=True):
        if totensor:
            try:
                self.X1 = torch.tensor(X1)
                self.X2 = torch.tensor(X2)
                self.Y = torch.tensor(Y)
            except:
                raise RuntimeError("Failed to convert input into torch.Tensor.")
        else:
            self.X1 = X1
            self.X2 = X2
            self.Y = Y

    def __getitem__(self, item):
        return self.X1[item], self.X2[item], self.Y[item]

    def __len__(self):
        return len(self.Y)

    def tolist(self):
        if not isinstance(self.X1, torch.Tensor):
            return self.X1, self.X2, self.Y
        return self.X1.tolist(), self.X2.tolist(), self.Y.tolist()

class XDataset(Dataset):
    def __init__(self, X=[], totensor=True):
        if totensor:
            try:
                self.X = torch.tensor(X)
            except:
                raise RuntimeError("Failed to convert input into torch.Tensor.")
        else:
            self.X = X

    def __getitem__(self, item):
        return self.X[item]

    def __len__(self):
        return len(self.X)
