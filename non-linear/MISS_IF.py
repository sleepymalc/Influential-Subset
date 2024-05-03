import torch
from pydvl.influence.torch import EkfacInfluence
from utlis.grad_calculator import count_parameters, grad_calculator
from utlis.data import data_generation
from tqdm import tqdm
import re

class MISS_IF:
    def __init__(self,
                 model,
                 model_checkpoints,
                 train_loader,
                 test_loader,
                 model_output_class,
                 device):
        '''
        :param model: a nn.module instance, no need to load any checkpoint
        :param model_checkpoints: a list of checkpoint path, the length of this list indicates the ensemble model number
        :param train_loader: train samples in a data loader
        :param train_loader: test samples in a data loader
        :param model_output_class: a class definition inheriting BaseModelOutputClass
        :param device: the device running
        '''
        self.model = model
        self.model_cpy = model

        self.model_checkpoints = model_checkpoints
        self.model_checkpoints_cpy = model_checkpoints

        self.train_loader = train_loader
        self.train_loader_cpy = train_loader

        self.test_loader = test_loader
        self.test_loader_cpy = test_loader

        self.model_output_class = model_output_class
        self.device = device
        self.warm_start = True



    def _convert_from_loader(self, loader):
        data = [(features, labels) for features, labels in loader]
        # for batch in loader:
        #     features, labels = batch
        #     data.append((features, labels))

        concatenated_data = [torch.cat([item[i] for item in data], dim=0) for i in range(len(data[0]))]

        return concatenated_data

    def _reset(self):
        self.model = self.model_cpy
        self.model_checkpoints = self.model_checkpoints_cpy
        self.train_loader = self.train_loader_cpy
        self.test_loader = self.test_loader_cpy


    def most_k(self, k):
        '''
        Select the most influential k samples
        '''

        influence_list = []

        train_data = self._convert_from_loader(self.train_loader)

        for checkpoint_id, checkpoint_file in enumerate(tqdm(self.model_checkpoints)):
            self.model.load_state_dict(torch.load(checkpoint_file))
            self.model.eval()
            influence_model = EkfacInfluence(
                self.model,
                update_diagonal=True,
                hessian_regularization=0.001,
            )
            influence_model = influence_model.fit(self.train_loader)

            parameters = list(self.model.parameters())
            normalize_factor = torch.sqrt(torch.tensor(count_parameters(self.model), dtype=torch.float32))

            all_grads_test_p = grad_calculator(data_loader=self.test_loader, model=self.model, parameters=parameters, func=self.model_output_class.model_output, normalize_factor=normalize_factor, device=self.device, projector=None, checkpoint_id=checkpoint_id)

            influence_factors = influence_model.influence_factors(*train_data)

            influence_list.append(influence_factors @ all_grads_test_p.T)

        influence_list_tensor = torch.stack(influence_list)
        influence = torch.mean(influence_list_tensor, dim=0)

        test_size = len(self.test_loader)
        MISS = torch.zeros(test_size, k, dtype=torch.int32)

        # Sort and get the indices of top k influential samples for each test sample
        print("Start TRAK greedy")
        for i in tqdm(range(test_size)):
            MISS[i, :] = torch.topk(influence[i], k).indices

        self._reset()
        return MISS

    # def adaptive_most_k(self, k):
    #     test_size = len(self.test_loader)
    #     train_size = len(self.train_loader)
    #     ensemble_num = len(self.model_checkpoints)
    #     seed = int(re.search(r'seed_(\d+)_ensemble_(\d+)', self.model_checkpoints[0]).group(1))
    #     MISS = torch.zeros(test_size, k, dtype=torch.int32)


    #     for j in tqdm(range(test_size)):
    #         model = self.model
    #         model_checkpoints = self.model_checkpoints
    #         index = list(range(train_size))
    #         for i in range(k):
    #             train_loader, test_loader = data_generation([i for i in range(train_size) if i not in MISS[j, :k]], list(range(test_size)), mode='MISS')
    #             IF = MISS_IF(model=model,
    #                          model_checkpoints=model_checkpoints,
    #                          train_loader=train_loader,
    #                          test_loader=test_loader,
    #                          model_output_class=self.model_output_class,
    #                          device=self.device)
    #             max_idx = IF.most_k(1)[j, 0]
    #             MISS[j, i] = index[max_idx]
    #             index = index[:max_idx] + index[max_idx + 1:]

    #             # update the model, the dataset
    #             for idx, checkpoint_file in enumerate(model_checkpoints):
    #                 if self.warm_start:
    #                     model.load_state_dict(torch.load(checkpoint_file))
    #                     epochs = 5
    #                 else:
    #                     epochs = 30
    #                 train_loader, test_loader = data_generation([i for i in range(train_size) if i not in MISS[j, :k]], list(range(test_size)), mode='train')

    #                 model.train_with_seed(train_loader, epochs=epochs, seed=idx, verbose=False)
    #                 torch.save(model.state_dict(), f"./checkpoint/tmp/seed_{seed}_{idx}.pt")

    #             model_checkpoints = [f"./checkpoint/tmp/seed_{seed}_{ensemble_idx}.pt" for ensemble_idx in range(ensemble_num)]

    #     return MISS

    def adaptive_most_k(self, k):
        test_size = len(self.test_loader)
        train_size = len(self.train_loader)
        ensemble_num = len(self.model_checkpoints)
        seed = int(re.search(r'seed_(\d+)_ensemble_(\d+)', self.model_checkpoints[0]).group(1))
        MISS = torch.zeros(test_size, k, dtype=torch.int32)

        for j in tqdm(range(test_size)):
            index = list(range(train_size))
            for i in range(k):
                train_loader, test_loader = data_generation([i for i in range(train_size) if i not in MISS[j, :k]], list(range(test_size)), mode='MISS')

                # most_k depends on self.train_loader and self.test_loader
                self.train_loader = train_loader
                self.test_loader = test_loader

                max_idx = self.most_k(1)[j, 0]
                MISS[j, i] = index[max_idx]
                index = index[:max_idx] + index[max_idx + 1:]

                # update the model, the dataset
                for idx, checkpoint_file in enumerate(self.model_checkpoints):
                    if self.warm_start:
                        self.model.load_state_dict(torch.load(checkpoint_file))
                        epochs = 8
                    else:
                        epochs = 30
                    train_loader, test_loader = data_generation([i for i in range(train_size) if i not in MISS[j, :k]], list(range(test_size)), mode='train')

                    self.model.train_with_seed(train_loader, epochs=epochs, seed=idx, verbose=False)
                    torch.save(self.model.state_dict(), f"./checkpoint/tmp/seed_{seed}_{idx}.pt")

                self.model_checkpoints = [f"./checkpoint/tmp/seed_{seed}_{ensemble_idx}.pt" for ensemble_idx in range(ensemble_num)]
            self._reset()

        return MISS