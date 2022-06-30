"""
the rules of naming records
M: model
R: communication round
B: batch size
E: local epoch
NS: number of local update steps
LR: learning rate (step size)
P: the proportion of selected clients in each round
S: random seed
LD: learning rate scheduler + learning rate decay
WD: weight decay
DR: the degree of dropout of clients
AC: the active rate of clients
"""
# import matplotlib
# matplotlib.rcParams['pdf.fonttype'] = 42
# matplotlib.rcParams['ps.fonttype'] = 42

import matplotlib.font_manager
from matplotlib import rc
#rc('font',**{'family':'sans-serif','sans-serif':['Helvetica']})


rc('font', **{'family': 'Times New Roman', 'serif': ['CMU Serif']})
rc('text')
import matplotlib.pyplot as plt
import json
import prettytable as pt
import os
import numpy as np

def read_data_into_dicts(task, records):
    path = '../fedtask/'+task+'/record'
    files = os.listdir(path)
    res = []
    for f in records:
        if f in files:
            file_path = os.path.join(path, f)
            with open(file_path, 'r') as inf:
                s_inf = inf.read()
                rec = json.loads(s_inf)
            res.append(rec)
    return res

#moi
# https://stackoverflow.com/questions/5283649/plot-smooth-line-with-pyplot
def smooth(scalars, weight):  # Weight between 0 and 1
    last = scalars[0]  # First value in the plot (first timestep)
    smoothed = list()
    for point in scalars:
        smoothed_val = last * weight + (1 - weight) * point  # Calculate smoothed value
        smoothed.append(smoothed_val)  # Save it
        last = smoothed_val  # Anchor the last smoothed value

    return smoothed
#moi

def draw_curve(dicts, curve='train_loss', legends = [], final_round = -1):
    # plt.figure(figsize=(100,100), dpi=100)
    print(legends)
    def removee(elem):
        a_string = elem
        new_string = a_string.replace("_z2", "")
        new_string2 = new_string.replace("_eta0.5", "")
        new_string3 = new_string2.replace("_eta1.0", "")
        return new_string3
    def removee2(elem):
        a_string = elem
        new_string = a_string.replace("_z2", "")
        #new_string2 = new_string.replace("_eta0.5", "")
        #new_string3 = new_string2.replace("_eta1.0", "")
        return new_string

    if eta == False:
        legends = [removee(item) for item in legends]
    else:
        legends = [removee2(item) for item in legends]


    if not legends: legends = [d['meta']['algorithm'] for d in dicts]
    for i,dict in enumerate(dicts):
        num_rounds = dict['meta']['num_rounds']
        eval_interval = dict['meta']['eval_interval']
        x = []
        for round in range(num_rounds + 1):
            if eval_interval > 0 and (round == 0 or round % eval_interval == 0 or round == num_rounds):
                x.append(round)
        y = dict[curve]
        #plt.plot(x, smooth(y, xx), label=legends[i], linewidth=1)
        #plt.plot(x, smooth(y, xx), label=legends[i], linewidth=w)
        if eta == False:
            if dict['meta']['algorithm'] == 'fedprox':
                zo = 10
                color = 'turquoise'
            if dict['meta']['algorithm'] == 'fedavg':
                zo = 9
                color = 'royalblue'
            if dict['meta']['algorithm'] == 'qfedavg':
                zo = 8
                color = 'darkorange'
            if dict['meta']['algorithm'] == 'scaffold':
                zo = 7
                color = 'red'
            plt.plot(x, smooth(y, xx), label=legends[i], linewidth=w, zorder=zo, color=color)
        else:
            plt.plot(x, smooth(y, xx), label=legends[i], linewidth=w)

        if final_round>0: plt.xlim((0, final_round))
    plt.legend(loc='lower left').set_zorder(20)
    # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=1)
    return

def filename_filter(fnames=[], filter={}):
    if filter:
        for key in filter.keys():
            con = filter[key].strip()
            if con[0] in ['[','{','(']:
                con = 'in ' + con
            elif '0'<=con[0]<='9' or con[0]=='.' or con[0]=='-':
                con = '==' + con
            elif 'a'<=con[0]<='z' or 'A'<=con[0]<='Z':
                con = "'"+con+"'"
            res = []
            for f in fnames:
                if f.find('_' + key)==-1: continue
                if eval(f[f.find('_' + key) + len(key) + 1:f.find('_', f.find('_' + key) + 1)] + ' ' + con):
                    res.append(f)
            fnames = res
    return fnames

def round_to_achieve_test_acc(records, dicts, target=0):
    tb= pt.PrettyTable()
    tb.field_names = [
        'Record',
        'Round to Achieve {}% Test-Acc.'.format(target),
    ]
    for rec, d in zip(records, dicts):
        r = -1
        for i in range(len(d['test_accuracy'])):
            if d['test_accuracy'][i]>=target-0.000001:
                r = i*d['meta']['eval_interval']
                break
        tb.add_row([rec, r])
    print(tb)
    return

def scan_records(task, header = '', filter = {}):
    path = '../fedtask/' + task + '/record'
    files = os.listdir(path)
    # check headers
    files = [f for f in files if f.startswith(header+'_') and f.endswith('.json')]
    return filename_filter(files, filter)

def print_table(records, dicts):
    tb = pt.PrettyTable()
    tb.field_names = [
        'Record',
        'Test-Acc.',
        'Valid-Acc.',
        'Train-Loss',
        'Test-Loss',
        'Best Test-Acc./Round',
        'Highest Valid-Acc.',
        'Lowest Valid-Acc.',
        'Mean-Valid-Acc.',
        'Var-Valid-Acc.',
    ]
    for rec,d in zip(records, dicts):
        testacc  = d['test_accuracy'][-1]
        validacc = d['mean_valid_accuracy'][-1]
        trainloss = d['train_loss'][-1]
        testloss = d['test_loss'][-1]
        bestacc = 0
        idx = -1
        for i in range(len(d['test_accuracy'])):
            if d['test_accuracy'][i]>bestacc:
                bestacc = d['test_accuracy'][i]
                idx = i*d['meta']['eval_interval']
        highest = float(np.max(d['valid_accuracy'][-1]))
        lowest = float(np.min(d['valid_accuracy'][-1]))
        mean_valid = float(np.mean(d['valid_accuracy'][-1]))
        var_valid = float(np.std(d['valid_accuracy'][-1]))
        tb.add_row([rec, testacc, validacc, trainloss, testloss, str(bestacc)+'/'+str(idx), highest, lowest, mean_valid, var_valid])
    tb.sortby = 'Test-Acc.'
    tb.reversesort = True
    print(tb)

def get_key_from_filename(record, key = ''):
    if key=='': return ''
    value_start = record.find('_'+key)+len(key)+1
    value_end = record.find('_',value_start)
    return record[value_start:value_end]

def create_legend(records=[], keys=[]):
    if records==[] or keys==[]:
        return records
    res = []
    for rec in records:
        s = [rec[:rec.find('_M')]]
        values = [k+get_key_from_filename(rec, k) for k in keys]
        s.extend(values)
        res.append(" ".join(s))
    return res


w=2.5
xx= 0.2
eta = True
eta = False
if __name__ == '__main__':
    # task+record
    task = 'cifar10_classification_cnum5_dist6_skew900.0_seed0'
    headers = [
        #'fedavg','fedprox','qfedavg',
        'fedavg',
        'fedprox',
        'qfedavg',
        'scaffold',
    ]
    flt = {
        # 'E': '1',
        # 'LR': '0.01',
        # 'R': '30',
        # 'P': '0.01',
        # 'S': '0',
        'z': '2',
        #'B':'16.0',
    }
    # read and filter the filenames
    records = set()
    for h in headers:
        records = records.union(set(scan_records(task, h, flt)))
    records = list(records)
    # read the selected files into dicts
    dicts = read_data_into_dicts(task, records)

    # print table
    print_table(records, dicts)

    # draw curves
    curve_names = [
        #'train_loss',
        #'test_loss',
        'test_accuracy',

        #'std_valid_loss',
        #'std_valid_accuracy',
    ]
    # create legends
    #legends = create_legend(records, ['B','LR','NS', 'E'])
    legends = create_legend(records, [''])
    i=0
    for curve in curve_names:

        plt.figure(i)

        draw_curve(dicts, curve, legends, 100)

        i = i + 1
        plt.title(task)
        plt.xlabel("communication_rounds")
        plt.ylabel(curve)
        ax = plt.gca()
        plt.grid()
    plt.show()

