import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, roc_auc_score, average_precision_score,
                             balanced_accuracy_score, recall_score, brier_score_loss, log_loss, classification_report)
import netcal.metrics


def eval_metrics(preds, targets, attributes, gs, thres=0.5, skip_per_attr=False):
    preds_rounded = preds >= thres if preds.squeeze().ndim == 1 else preds.argmax(1)
    label_set = np.unique(targets)
    preds_at_targets = preds[:, 1] if len(label_set) == 2 else preds

    res = {}
    res['overall'] = {
        **binary_metrics(targets, preds_rounded, label_set),
        **prob_metrics(targets, preds_at_targets, label_set)
    }
    res['per_attribute'] = {}
    res['per_class'] = {}
    res['per_group'] = {}

    if not skip_per_attr:
        for a in np.unique(attributes):
            mask = attributes == a
            res['per_attribute'][int(a)] = {
                **binary_metrics(targets[mask], preds_rounded[mask], label_set),
                **prob_metrics(targets[mask], preds_at_targets[mask], label_set)
            }

    classes_report = classification_report(targets, preds_rounded, output_dict=True, zero_division=0.)
    res['overall']['macro_avg'] = classes_report['macro avg']
    res['overall']['weighted_avg'] = classes_report['weighted avg']
    for y in np.unique(targets):
        res['per_class'][int(y)] = classes_report[str(y)]

    for g in np.unique(gs):
        mask = gs == g
        res['per_group'][g] = {
            **binary_metrics(targets[mask], preds_rounded[mask], label_set)
        }

    res['adjusted_accuracy'] = sum([res['per_group'][g]['accuracy'] for g in np.unique(gs)]) / len(np.unique(gs))
    if not skip_per_attr:
        res['min_attr'] = pd.DataFrame(res['per_attribute']).min(axis=1).to_dict()
        res['max_attr'] = pd.DataFrame(res['per_attribute']).max(axis=1).to_dict()
    res['min_group'] = pd.DataFrame(res['per_group']).min(axis=1).to_dict()
    res['max_group'] = pd.DataFrame(res['per_group']).max(axis=1).to_dict()

    return res


def binary_metrics(targets, preds, label_set=(0, 1), return_arrays=False):
    if len(targets) == 0:
        return {}

    res = {
        'accuracy': accuracy_score(targets, preds),
        'n_samples': len(targets)
    }

    if len(label_set) == 2:
        CM = confusion_matrix(targets, preds, labels=label_set)

        res['TN'] = CM[0][0].item()
        res['FN'] = CM[1][0].item()
        res['TP'] = CM[1][1].item()
        res['FP'] = CM[0][1].item()
        res['error'] = res['FN'] + res['FP']

        if res['TP'] + res['FN'] == 0:
            res['TPR'] = 0
            res['FNR'] = 1
        else:
            res['TPR'] = res['TP'] / (res['TP'] + res['FN'])
            res['FNR'] = res['FN'] / (res['TP'] + res['FN'])

        if res['FP'] + res['TN'] == 0:
            res['FPR'] = 1
            res['TNR'] = 0
        else:
            res['FPR'] = res['FP'] / (res['FP'] + res['TN'])
            res['TNR'] = res['TN'] / (res['FP'] + res['TN'])

        res['pred_prevalence'] = (res['TP'] + res['FP']) / res['n_samples']
        res['prevalence'] = (res['TP'] + res['FN']) / res['n_samples']
    else:
        CM = confusion_matrix(targets, preds, labels=label_set)
        res['TPR'] = recall_score(targets, preds, labels=label_set, average='macro', zero_division=0.)

    if len(np.unique(targets)) > 1:
        res['balanced_acc'] = balanced_accuracy_score(targets, preds)

    if return_arrays:
        res['targets'] = targets
        res['preds'] = preds

    return res


def prob_metrics(targets, preds, label_set, return_arrays=False):
    if len(targets) == 0:
        return {}

    res = {
        'AUROC_ovo': roc_auc_score(targets, preds, multi_class='ovo', labels=label_set),
        'BCE': log_loss(targets, preds, labels=label_set),  # , eps=1e-6
        'ECE': netcal.metrics.ECE().measure(preds, targets)
    }

    # happens when you predict a class, but there are no samples with that class in the dataset
    try:
        res['AUROC'] = roc_auc_score(targets, preds, multi_class='ovr', labels=label_set)
    except:
        res['AUROC'] = roc_auc_score(targets, preds, multi_class='ovo', labels=label_set)

    if len(set(targets)) == 2:
        res['AUPRC'] = average_precision_score(targets, preds, average='macro')
        res['brier'] = brier_score_loss(targets, preds)

    if return_arrays:
        res['targets'] = targets
        res['preds'] = preds

    return res


def get_acc(preds, classes, groups):
    acc = preds == classes
    acc_groups = []
    for g in np.unique(groups):
        cond = groups == g
        acc_groups.append(np.round(sum(acc[cond]) / len(acc[cond]), 3))
    avg_acc = sum(acc) / len(acc)
    return avg_acc, acc_groups
